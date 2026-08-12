import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity, createTodo, completeTodos } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { status, keyword, orgId } = req.query;
  const where: Record<string, unknown> = {};
  if (status) where.status = String(status);
  if (orgId) where.orgId = String(orgId);
  if (keyword) {
    where.OR = [
      { name: { contains: String(keyword) } },
      { positionTitle: { contains: String(keyword) } },
    ];
  }
  const list = await prisma.recruitRequest.findMany({
    where,
    include: {
      org: true,
      hrOwner: { select: { id: true, name: true } },
      deptHead: { select: { id: true, name: true } },
      jobs: { select: { id: true, title: true, status: true, headcount: true, hiredCount: true } },
    },
    orderBy: { updatedAt: 'desc' },
  });
  res.json(list);
});

router.get('/:id', authRequired, async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({
    where: { id: req.params.id },
    include: {
      org: true,
      hrOwner: true,
      deptHead: true,
      owner: true,
      jobs: true,
    },
  });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  res.json(item);
});

router.post('/', authRequired, requireRoles('HR', 'DEPT_HEAD', 'RECRUIT_LEAD'), async (req, res) => {
  const body = req.body;
  if (!body.positionTitle || !body.orgId || !body.headcount || !body.reason || !body.expectDate || !body.workLocation) {
    return res.status(400).json({ message: '请填写必填字段：岗位、部门、人数、原因、到岗日期、地点' });
  }
  if (Number(body.headcount) <= 0) return res.status(400).json({ message: '需求人数必须大于0' });
  if (body.salaryMin != null && body.salaryMax != null && Number(body.salaryMin) > Number(body.salaryMax)) {
    return res.status(400).json({ message: '薪资最低值不得大于最高值' });
  }
  const expectDate = new Date(body.expectDate);
  if (expectDate < new Date(new Date().toDateString())) {
    return res.status(400).json({ message: '期望到岗日期不得早于当前日期' });
  }
  const org = await prisma.organization.findUnique({ where: { id: body.orgId } });
  const name = body.name || `${org?.name || ''}${body.positionTitle}${body.headcount}人`;
  const item = await prisma.recruitRequest.create({
    data: {
      name,
      orgId: body.orgId,
      positionTitle: body.positionTitle,
      headcount: Number(body.headcount),
      reason: body.reason,
      expectDate,
      workLocation: body.workLocation,
      salaryMin: body.salaryMin != null ? Number(body.salaryMin) : null,
      salaryMax: body.salaryMax != null ? Number(body.salaryMax) : null,
      deptHeadId: body.deptHeadId || req.user!.id,
      description: body.description,
      status: body.submit ? 'PENDING' : 'DRAFT',
      ownerId: req.user!.id,
    },
  });
  if (body.submit) {
    const approvers = await prisma.user.findMany({
      where: { role: { in: ['RECRUIT_LEAD', 'ADMIN'] }, active: true },
    });
    for (const a of approvers) {
      await createTodo({
        userId: a.id,
        type: 'APPROVE_REQUEST',
        title: `审批招聘需求：${item.name}`,
        refType: 'RecruitRequest',
        refId: item.id,
      });
    }
  }
  await writeAudit(req, body.submit ? '提交审批' : '新建草稿', 'RecruitRequest', item.id, null, item);
  res.json(item);
});

router.put('/:id', authRequired, async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (!['DRAFT', 'REJECTED'].includes(item.status)) {
    return res.status(400).json({ message: '审批中或已通过的需求不可直接修改，请先撤回' });
  }
  const body = req.body;
  const updated = await prisma.recruitRequest.update({
    where: { id: item.id },
    data: {
      name: body.name ?? item.name,
      orgId: body.orgId ?? item.orgId,
      positionTitle: body.positionTitle ?? item.positionTitle,
      headcount: body.headcount != null ? Number(body.headcount) : item.headcount,
      reason: body.reason ?? item.reason,
      expectDate: body.expectDate ? new Date(body.expectDate) : item.expectDate,
      workLocation: body.workLocation ?? item.workLocation,
      salaryMin: body.salaryMin != null ? Number(body.salaryMin) : item.salaryMin,
      salaryMax: body.salaryMax != null ? Number(body.salaryMax) : item.salaryMax,
      deptHeadId: body.deptHeadId ?? item.deptHeadId,
      description: body.description ?? item.description,
      status: body.submit ? 'PENDING' : item.status === 'REJECTED' ? 'DRAFT' : item.status,
      rejectReason: body.submit ? null : item.rejectReason,
    },
  });
  if (body.submit) {
    const approvers = await prisma.user.findMany({
      where: { role: { in: ['RECRUIT_LEAD', 'ADMIN'] }, active: true },
    });
    for (const a of approvers) {
      await createTodo({
        userId: a.id,
        type: 'APPROVE_REQUEST',
        title: `审批招聘需求：${updated.name}`,
        refType: 'RecruitRequest',
        refId: updated.id,
      });
    }
  }
  await writeAudit(req, '编辑需求', 'RecruitRequest', item.id, item, updated);
  res.json(updated);
});

router.post('/:id/withdraw', authRequired, async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (item.status !== 'PENDING') return res.status(400).json({ message: '仅审批中的需求可撤回' });
  const updated = await prisma.recruitRequest.update({
    where: { id: item.id },
    data: { status: 'DRAFT' },
  });
  await completeTodos('RecruitRequest', item.id, 'APPROVE_REQUEST');
  await writeAudit(req, '撤回审批', 'RecruitRequest', item.id, item, updated);
  res.json(updated);
});

router.post('/:id/approve', authRequired, requireRoles('RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (item.status !== 'PENDING') return res.status(400).json({ message: '当前状态不可审批' });
  const { action, comment, hrOwnerId } = req.body;
  if (action === 'reject') {
    if (!comment) return res.status(400).json({ message: '驳回必须填写原因' });
    const updated = await prisma.recruitRequest.update({
      where: { id: item.id },
      data: { status: 'REJECTED', rejectReason: comment, approvalComment: comment },
    });
    await completeTodos('RecruitRequest', item.id, 'APPROVE_REQUEST');
    await writeAudit(req, '驳回需求', 'RecruitRequest', item.id, item, updated, comment);
    return res.json(updated);
  }
  const updated = await prisma.recruitRequest.update({
    where: { id: item.id },
    data: {
      status: 'APPROVED',
      approvalComment: comment,
      approvedAt: new Date(),
      approvedBy: req.user!.id,
      hrOwnerId: hrOwnerId || item.hrOwnerId,
    },
  });
  await completeTodos('RecruitRequest', item.id, 'APPROVE_REQUEST');
  await writeAudit(req, '同意需求', 'RecruitRequest', item.id, item, updated, comment);
  await writeActivity({
    type: 'REQUEST_APPROVED',
    title: `招聘需求已通过：${updated.name}`,
    actorId: req.user!.id,
    actorName: req.user!.name,
    relatedId: updated.id,
  });
  res.json(updated);
});

router.post('/:id/assign', authRequired, requireRoles('RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (!['APPROVED', 'RECRUITING'].includes(item.status)) {
    return res.status(400).json({ message: '仅已通过或招聘中的需求可分配负责人' });
  }
  if (!req.body.hrOwnerId) return res.status(400).json({ message: '请指定招聘HR' });
  const updated = await prisma.recruitRequest.update({
    where: { id: item.id },
    data: { hrOwnerId: req.body.hrOwnerId, status: item.status === 'APPROVED' ? 'RECRUITING' : item.status },
  });
  await writeAudit(req, '分配招聘HR', 'RecruitRequest', item.id, item, updated, req.body.reason);
  res.json(updated);
});

router.post('/:id/close', authRequired, requireRoles('RECRUIT_LEAD', 'ADMIN', 'HR'), async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (!req.body.reason) return res.status(400).json({ message: '关闭必须填写原因' });
  const updated = await prisma.recruitRequest.update({
    where: { id: item.id },
    data: { status: 'CLOSED', closeReason: req.body.reason },
  });
  await writeAudit(req, '关闭需求', 'RecruitRequest', item.id, item, updated, req.body.reason);
  res.json(updated);
});

router.post('/:id/reopen', authRequired, requireRoles('RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (item.status !== 'CLOSED') return res.status(400).json({ message: '仅已关闭需求可重开' });
  const updated = await prisma.recruitRequest.update({
    where: { id: item.id },
    data: { status: 'RECRUITING', closeReason: null },
  });
  await writeAudit(req, '重开需求', 'RecruitRequest', item.id, item, updated, req.body.reason);
  res.json(updated);
});

router.delete('/:id', authRequired, async (req, res) => {
  const item = await prisma.recruitRequest.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '需求不存在' });
  if (item.status !== 'DRAFT') return res.status(400).json({ message: '仅草稿可删除' });
  await prisma.recruitRequest.delete({ where: { id: item.id } });
  await writeAudit(req, '删除草稿', 'RecruitRequest', item.id, item, null);
  res.json({ ok: true });
});

export default router;
