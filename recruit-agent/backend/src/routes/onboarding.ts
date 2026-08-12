import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity, completeTodos, addProcessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { status, keyword } = req.query;
  const where: Record<string, unknown> = {};
  if (status) where.status = String(status);
  const list = await prisma.onboarding.findMany({
    where,
    include: {
      application: {
        include: {
          candidate: true,
          job: { include: { org: true } },
        },
      },
      offer: true,
    },
    orderBy: { expectedDate: 'asc' },
  });
  const filtered = keyword
    ? list.filter((o) => o.application.candidate.name.includes(String(keyword)))
    : list;
  res.json(filtered);
});

router.get('/:id', authRequired, async (req, res) => {
  const item = await prisma.onboarding.findUnique({
    where: { id: req.params.id },
    include: {
      application: { include: { candidate: true, job: { include: { org: true } } } },
      offer: true,
    },
  });
  if (!item) return res.status(404).json({ message: '待入职记录不存在' });
  res.json({
    ...item,
    materials: item.materials ? JSON.parse(item.materials) : [],
  });
});

router.post('/:id/confirm', authRequired, requireRoles('HR_OPS', 'HR', 'ADMIN'), async (req, res) => {
  const item = await prisma.onboarding.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  const updated = await prisma.onboarding.update({
    where: { id: item.id },
    data: {
      status: 'CONFIRMED',
      confirmedDate: req.body.confirmedDate ? new Date(req.body.confirmedDate) : new Date(),
      actualDate: req.body.actualDate ? new Date(req.body.actualDate) : item.expectedDate,
      contactPerson: req.body.contactPerson,
      followRemark: req.body.followRemark,
    },
  });
  res.json(updated);
});

router.put('/:id/materials', authRequired, requireRoles('HR_OPS', 'HR', 'ADMIN'), async (req, res) => {
  const item = await prisma.onboarding.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  const updated = await prisma.onboarding.update({
    where: { id: item.id },
    data: { materials: JSON.stringify(req.body.materials || []) },
  });
  res.json({ ...updated, materials: req.body.materials });
});

router.post('/:id/delay', authRequired, requireRoles('HR_OPS', 'HR', 'ADMIN'), async (req, res) => {
  const item = await prisma.onboarding.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  if (!req.body.reason || !req.body.expectedDate) {
    return res.status(400).json({ message: '延期需更新日期并填写原因' });
  }
  const updated = await prisma.onboarding.update({
    where: { id: item.id },
    data: {
      status: 'DELAYED',
      expectedDate: new Date(req.body.expectedDate),
      delayReason: req.body.reason,
      followRemark: req.body.followRemark,
    },
  });
  await writeAudit(req, '入职延期', 'Onboarding', item.id, item, updated, req.body.reason);
  res.json(updated);
});

router.post('/:id/abandon', authRequired, requireRoles('HR_OPS', 'HR', 'ADMIN'), async (req, res) => {
  const item = await prisma.onboarding.findUnique({
    where: { id: req.params.id },
    include: { application: true },
  });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  if (!req.body.reason) return res.status(400).json({ message: '放弃需选择原因' });
  const updated = await prisma.onboarding.update({
    where: { id: item.id },
    data: { status: 'ABANDONED', abandonReason: req.body.reason },
  });
  await prisma.application.update({
    where: { id: item.applicationId },
    data: { status: 'WITHDRAWN', rejectReason: req.body.reason },
  });
  await completeTodos('Onboarding', item.id);
  await addProcessEvent({
    applicationId: item.applicationId,
    type: 'ABANDON',
    fromStatus: item.application.status,
    toStatus: 'WITHDRAWN',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    reason: req.body.reason,
  });
  await writeAudit(req, '放弃入职', 'Onboarding', item.id, item, updated, req.body.reason);
  res.json(updated);
});

router.post('/:id/hire', authRequired, requireRoles('HR_OPS', 'ADMIN'), async (req, res) => {
  const item = await prisma.onboarding.findUnique({
    where: { id: req.params.id },
    include: {
      application: { include: { candidate: true, job: { include: { request: true } } } },
      offer: true,
    },
  });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  if (['HIRED', 'ABANDONED'].includes(item.status)) {
    return res.status(400).json({ message: '终态不可重复确认入职' });
  }
  if (!req.body.actualDate) return res.status(400).json({ message: '请填写实际入职日期' });

  const employeeNo = req.body.employeeNo || `E${Date.now().toString().slice(-8)}`;
  const updated = await prisma.onboarding.update({
    where: { id: item.id },
    data: {
      status: 'HIRED',
      actualDate: new Date(req.body.actualDate),
      employeeNo,
    },
  });

  await prisma.application.update({
    where: { id: item.applicationId },
    data: { status: 'HIRED' },
  });

  const job = item.application.job;
  const newHired = job.hiredCount + 1;
  await prisma.job.update({
    where: { id: job.id },
    data: {
      hiredCount: newHired,
      status: newHired >= job.headcount ? 'CLOSED' : job.status,
    },
  });

  if (job.requestId) {
    const request = job.request;
    const reqHired = request.hiredCount + 1;
    await prisma.recruitRequest.update({
      where: { id: request.id },
      data: {
        hiredCount: reqHired,
        status: reqHired >= request.headcount ? 'COMPLETED' : request.status,
      },
    });
  }

  await completeTodos('Onboarding', item.id);
  await addProcessEvent({
    applicationId: item.applicationId,
    type: 'HIRED',
    fromStatus: 'ONBOARDING',
    toStatus: 'HIRED',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    detail: `员工编号 ${employeeNo}`,
  });
  await writeActivity({
    type: 'HIRED',
    title: `${item.application.candidate.name} 已入职`,
    jobId: job.id,
    relatedId: item.id,
    actorId: req.user!.id,
    actorName: req.user!.name,
  });
  await writeAudit(req, '确认入职', 'Onboarding', item.id, item, updated);

  const archive = {
    employeeNo,
    name: item.application.candidate.name,
    phone: item.application.candidate.phone,
    email: item.application.candidate.email,
    department: job.orgId,
    title: job.title,
    hireDate: req.body.actualDate,
    baseSalary: item.offer?.baseSalary,
    workLocation: item.offer?.workLocation,
  };

  res.json({
    onboarding: updated,
    employeeArchive: archive,
    tips:
      newHired >= job.headcount
        ? '已达到职位招聘人数，职位已自动关闭；请确认是否关闭关联需求。'
        : undefined,
  });
});

router.get('/:id/archive-export', authRequired, requireRoles('HR_OPS', 'ADMIN', 'HR'), async (req, res) => {
  const item = await prisma.onboarding.findUnique({
    where: { id: req.params.id },
    include: {
      application: { include: { candidate: true, job: { include: { org: true } } } },
      offer: true,
    },
  });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  const archive = {
    employeeNo: item.employeeNo,
    name: item.application.candidate.name,
    phone: item.application.candidate.phone,
    email: item.application.candidate.email,
    education: item.application.candidate.education,
    department: item.application.job.org.name,
    title: item.application.job.title,
    hireDate: item.actualDate,
    expectedDate: item.expectedDate,
    workLocation: item.offer?.workLocation,
    level: item.offer?.level,
    baseSalary: item.offer?.baseSalary,
    materials: item.materials ? JSON.parse(item.materials) : [],
  };
  await writeAudit(req, '导出员工档案', 'Onboarding', item.id, null, archive);
  res.json(archive);
});

export default router;
