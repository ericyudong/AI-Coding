import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity, createTodo, completeTodos, addProcessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { status, keyword } = req.query;
  const where: Record<string, unknown> = {};
  if (status) where.status = String(status);
  const list = await prisma.offer.findMany({
    where,
    include: {
      application: {
        include: {
          candidate: true,
          job: { include: { org: true } },
        },
      },
    },
    orderBy: { updatedAt: 'desc' },
  });
  const filtered = keyword
    ? list.filter((o) => o.application.candidate.name.includes(String(keyword)) || o.application.job.title.includes(String(keyword)))
    : list;
  res.json(filtered);
});

router.get('/:id', authRequired, async (req, res) => {
  const item = await prisma.offer.findUnique({
    where: { id: req.params.id },
    include: {
      application: {
        include: {
          candidate: true,
          job: { include: { org: true } },
          interviews: { include: { evaluations: true } },
        },
      },
      onboarding: true,
    },
  });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  // mask salary for DATA_VIEWER
  if (req.user!.role === 'DATA_VIEWER') {
    return res.json({
      ...item,
      baseSalary: null,
      performance: null,
      bonus: null,
      probationSalary: null,
      _masked: true,
    });
  }
  res.json(item);
});

router.post('/', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const body = req.body;
  if (!body.applicationId) return res.status(400).json({ message: '请选择应聘记录' });
  const app = await prisma.application.findUnique({
    where: { id: body.applicationId },
    include: { candidate: true, job: true, offers: { where: { isActive: true } } },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (!['OFFER', 'INTERVIEW'].includes(app.status) && !body.force) {
    return res.status(400).json({ message: '仅终面通过或Offer阶段可创建Offer' });
  }
  if (app.offers.some((o) => !['DECLINED', 'EXPIRED', 'WITHDRAWN', 'REJECTED'].includes(o.status))) {
    return res.status(400).json({ message: '同一应聘记录同一时间只能存在一份有效Offer' });
  }
  if (!body.workLocation || body.baseSalary == null || !body.expectedHireDate) {
    return res.status(400).json({ message: '请填写工作地点、基本工资、拟入职日期' });
  }

  // deactivate old
  await prisma.offer.updateMany({
    where: { applicationId: app.id, isActive: true },
    data: { isActive: false },
  });

  const maxVersion = await prisma.offer.aggregate({
    where: { applicationId: app.id },
    _max: { version: true },
  });

  const offer = await prisma.offer.create({
    data: {
      applicationId: app.id,
      version: (maxVersion._max.version || 0) + 1,
      isActive: true,
      reportTo: body.reportTo,
      level: body.level,
      workLocation: body.workLocation,
      baseSalary: Number(body.baseSalary),
      performance: body.performance != null ? Number(body.performance) : null,
      bonus: body.bonus != null ? Number(body.bonus) : null,
      probationMonths: body.probationMonths != null ? Number(body.probationMonths) : 3,
      probationSalary: body.probationSalary != null ? Number(body.probationSalary) : null,
      expectedHireDate: new Date(body.expectedHireDate),
      validUntil: body.validUntil ? new Date(body.validUntil) : null,
      otherTerms: body.otherTerms,
      approvalNote: body.approvalNote,
      status: body.submit ? 'PENDING' : 'DRAFT',
    },
  });

  await prisma.application.update({
    where: { id: app.id },
    data: { status: 'OFFER', stage: 'OFFER' },
  });

  if (body.submit) {
    const approvers = await prisma.user.findMany({
      where: { role: { in: ['OFFER_APPROVER', 'ADMIN', 'RECRUIT_LEAD'] }, active: true },
    });
    for (const a of approvers) {
      await createTodo({
        userId: a.id,
        type: 'APPROVE_OFFER',
        title: `审批Offer：${app.candidate.name} - ${app.job.title}`,
        refType: 'Offer',
        refId: offer.id,
      });
    }
  }
  await writeAudit(req, body.submit ? '提交Offer审批' : '创建Offer草稿', 'Offer', offer.id, null, offer);
  res.json(offer);
});

router.put('/:id', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.offer.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  if (!['DRAFT', 'REJECTED'].includes(item.status)) {
    return res.status(400).json({ message: '已审批Offer变更关键字段需复制为新版本重新审批' });
  }
  const body = req.body;
  const updated = await prisma.offer.update({
    where: { id: item.id },
    data: {
      reportTo: body.reportTo ?? item.reportTo,
      level: body.level ?? item.level,
      workLocation: body.workLocation ?? item.workLocation,
      baseSalary: body.baseSalary != null ? Number(body.baseSalary) : item.baseSalary,
      performance: body.performance != null ? Number(body.performance) : item.performance,
      bonus: body.bonus != null ? Number(body.bonus) : item.bonus,
      probationMonths: body.probationMonths != null ? Number(body.probationMonths) : item.probationMonths,
      probationSalary: body.probationSalary != null ? Number(body.probationSalary) : item.probationSalary,
      expectedHireDate: body.expectedHireDate ? new Date(body.expectedHireDate) : item.expectedHireDate,
      validUntil: body.validUntil ? new Date(body.validUntil) : item.validUntil,
      otherTerms: body.otherTerms ?? item.otherTerms,
      approvalNote: body.approvalNote ?? item.approvalNote,
      status: body.submit ? 'PENDING' : item.status,
    },
  });
  if (body.submit) {
    const app = await prisma.application.findUnique({
      where: { id: item.applicationId },
      include: { candidate: true, job: true },
    });
    const approvers = await prisma.user.findMany({
      where: { role: { in: ['OFFER_APPROVER', 'ADMIN', 'RECRUIT_LEAD'] }, active: true },
    });
    for (const a of approvers) {
      await createTodo({
        userId: a.id,
        type: 'APPROVE_OFFER',
        title: `审批Offer：${app?.candidate.name}`,
        refType: 'Offer',
        refId: updated.id,
      });
    }
  }
  res.json(updated);
});

router.post('/:id/revise', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.offer.findUnique({
    where: { id: req.params.id },
    include: { application: { include: { candidate: true, job: true } } },
  });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  if (!['APPROVED', 'SENT', 'REJECTED'].includes(item.status)) {
    return res.status(400).json({ message: '当前状态无需走变更版本' });
  }
  await prisma.offer.update({ where: { id: item.id }, data: { isActive: false } });
  const body = req.body;
  const offer = await prisma.offer.create({
    data: {
      applicationId: item.applicationId,
      version: item.version + 1,
      isActive: true,
      reportTo: body.reportTo ?? item.reportTo,
      level: body.level ?? item.level,
      workLocation: body.workLocation ?? item.workLocation,
      baseSalary: body.baseSalary != null ? Number(body.baseSalary) : item.baseSalary,
      performance: body.performance != null ? Number(body.performance) : item.performance,
      bonus: body.bonus != null ? Number(body.bonus) : item.bonus,
      probationMonths: body.probationMonths != null ? Number(body.probationMonths) : item.probationMonths,
      probationSalary: body.probationSalary != null ? Number(body.probationSalary) : item.probationSalary,
      expectedHireDate: body.expectedHireDate ? new Date(body.expectedHireDate) : item.expectedHireDate,
      validUntil: body.validUntil ? new Date(body.validUntil) : item.validUntil,
      otherTerms: body.otherTerms ?? item.otherTerms,
      status: 'DRAFT',
    },
  });
  await writeAudit(req, '创建Offer新版本', 'Offer', offer.id, item, offer, body.reason);
  res.json(offer);
});

router.post('/:id/approve', authRequired, requireRoles('OFFER_APPROVER', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.offer.findUnique({
    where: { id: req.params.id },
    include: { application: { include: { candidate: true, job: true } } },
  });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  if (item.status !== 'PENDING') return res.status(400).json({ message: '当前状态不可审批' });
  const { action, comment } = req.body;
  if (action === 'reject') {
    if (!comment) return res.status(400).json({ message: '驳回必须填写原因' });
    const updated = await prisma.offer.update({
      where: { id: item.id },
      data: { status: 'REJECTED', rejectReason: comment },
    });
    await completeTodos('Offer', item.id, 'APPROVE_OFFER');
    await writeAudit(req, '驳回Offer', 'Offer', item.id, item, updated, comment);
    return res.json(updated);
  }
  const updated = await prisma.offer.update({
    where: { id: item.id },
    data: { status: 'APPROVED', approvedAt: new Date(), approvedBy: req.user!.id, approvalNote: comment },
  });
  await completeTodos('Offer', item.id, 'APPROVE_OFFER');
  await writeAudit(req, '同意Offer', 'Offer', item.id, item, updated, comment);
  res.json(updated);
});

router.post('/:id/send', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.offer.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  if (item.status !== 'APPROVED') return res.status(400).json({ message: '仅已通过的Offer可记录发送' });
  const validUntil = req.body.validUntil ? new Date(req.body.validUntil) : item.validUntil;
  if (validUntil && item.sentAt && validUntil < new Date()) {
    // skip
  }
  const updated = await prisma.offer.update({
    where: { id: item.id },
    data: {
      status: 'SENT',
      sentAt: new Date(),
      sentBy: req.user!.id,
      validUntil: validUntil || new Date(Date.now() + 7 * 86400000),
    },
  });
  await writeAudit(req, '记录Offer发送', 'Offer', item.id, item, updated);
  res.json(updated);
});

router.get('/:id/preview', authRequired, async (req, res) => {
  const item = await prisma.offer.findUnique({
    where: { id: req.params.id },
    include: {
      application: { include: { candidate: true, job: { include: { org: true } } } },
    },
  });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  const c = item.application.candidate;
  const j = item.application.job;
  const text = `录用通知书（Offer）

尊敬的 ${c.name}：

诚挚邀请您加入本公司，担任「${j.title}」一职。

一、录用信息
- 部门：${j.org.name}
- 工作地点：${item.workLocation}
- 职级/序列：${item.level || '按公司规定'}
- 汇报对象：${item.reportTo || '待定'}
- 拟入职日期：${item.expectedHireDate.toISOString().slice(0, 10)}

二、薪酬结构
- 基本工资：${item.baseSalary} 元/月
- 绩效：${item.performance ?? '按制度'} 元/月
- 奖金：${item.bonus ?? '按制度'}
- 试用期：${item.probationMonths} 个月
- 试用期薪资：${item.probationSalary ?? item.baseSalary * 0.8} 元/月

三、其他约定
${item.otherTerms || '无'}

四、有效期
本Offer有效期至：${item.validUntil ? item.validUntil.toISOString().slice(0, 10) : '发送后7日内'}

请于有效期内确认是否接受。

（系统生成预览，正式文件由HR通过现有渠道发送）
`;
  res.json({ text, offer: item });
});

router.post('/:id/result', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.offer.findUnique({
    where: { id: req.params.id },
    include: { application: { include: { candidate: true, job: true } } },
  });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  if (!['SENT', 'APPROVED'].includes(item.status)) {
    return res.status(400).json({ message: '仅已发送/已通过Offer可记录结果' });
  }
  const { result, declineReason } = req.body;
  if (!['ACCEPTED', 'DECLINED', 'PENDING', 'EXPIRED'].includes(result)) {
    return res.status(400).json({ message: '无效结果' });
  }
  if (result === 'DECLINED' && !declineReason) {
    return res.status(400).json({ message: '拒绝需选择原因' });
  }

  const updated = await prisma.offer.update({
    where: { id: item.id },
    data: {
      status: result,
      declineReason,
      resultAt: new Date(),
    },
  });

  if (result === 'ACCEPTED') {
    const onboarding = await prisma.onboarding.create({
      data: {
        applicationId: item.applicationId,
        offerId: item.id,
        expectedDate: item.expectedHireDate,
        status: 'PENDING_CONFIRM',
        materials: JSON.stringify([
          { name: '身份证复印件', status: 'PENDING' },
          { name: '学历证明', status: 'PENDING' },
          { name: '离职证明', status: 'PENDING' },
          { name: '体检报告', status: 'PENDING' },
          { name: '银行卡信息', status: 'PENDING' },
        ]),
      },
    });
    await prisma.application.update({
      where: { id: item.applicationId },
      data: { status: 'ONBOARDING', stage: 'ONBOARDING' },
    });
    const ops = await prisma.user.findMany({ where: { role: { in: ['HR_OPS', 'ADMIN'] }, active: true } });
    for (const u of ops) {
      await createTodo({
        userId: u.id,
        type: 'ONBOARDING',
        title: `待入职跟进：${item.application.candidate.name}`,
        refType: 'Onboarding',
        refId: onboarding.id,
        dueAt: item.expectedHireDate,
      });
    }
    await addProcessEvent({
      applicationId: item.applicationId,
      type: 'OFFER_ACCEPTED',
      fromStatus: 'OFFER',
      toStatus: 'ONBOARDING',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
    });
    await writeActivity({
      type: 'OFFER_ACCEPTED',
      title: `${item.application.candidate.name} 已接受Offer`,
      jobId: item.application.jobId,
      relatedId: item.id,
      actorId: req.user!.id,
      actorName: req.user!.name,
    });
  } else if (result === 'DECLINED') {
    await prisma.application.update({
      where: { id: item.applicationId },
      data: { status: 'WITHDRAWN', rejectReason: declineReason },
    });
    await addProcessEvent({
      applicationId: item.applicationId,
      type: 'OFFER_DECLINED',
      fromStatus: 'OFFER',
      toStatus: 'WITHDRAWN',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      reason: declineReason,
    });
  }
  await writeAudit(req, `Offer结果:${result}`, 'Offer', item.id, item, updated, declineReason);
  res.json(updated);
});

router.post('/:id/withdraw', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.offer.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: 'Offer不存在' });
  if (!req.body.reason) return res.status(400).json({ message: '撤回必须填写原因' });
  const updated = await prisma.offer.update({
    where: { id: item.id },
    data: { status: 'WITHDRAWN', withdrawReason: req.body.reason, isActive: false },
  });
  await writeAudit(req, '撤回Offer', 'Offer', item.id, item, updated, req.body.reason);
  res.json(updated);
});

export default router;
