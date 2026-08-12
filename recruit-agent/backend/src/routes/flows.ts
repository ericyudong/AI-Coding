import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, createTodo, emitBusinessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (_req, res) => {
  const list = await prisma.flowTemplate.findMany({
    include: { nodes: { orderBy: { sort: 'asc' } } },
    orderBy: { updatedAt: 'desc' },
  });
  res.json(list);
});

router.post('/', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (req, res) => {
  const { name, description, nodes } = req.body;
  if (!name) return res.status(400).json({ message: '流程名称必填' });
  const tpl = await prisma.flowTemplate.create({
    data: {
      name,
      description,
      nodes: {
        create: (nodes || []).map((n: any, i: number) => ({
          key: n.key || `NODE_${i + 1}`,
          name: n.name,
          type: n.type || 'CUSTOM',
          sort: n.sort != null ? n.sort : i,
          required: n.required !== false,
          skippable: !!n.skippable,
          parallel: !!n.parallel,
          condition: n.condition,
          role: n.role,
          slaHours: n.slaHours,
          escalateRole: n.escalateRole,
          passCondition: n.passCondition,
          requiredFields: n.requiredFields,
        })),
      },
    },
    include: { nodes: true },
  });
  await writeAudit(req, '创建流程模板', 'FlowTemplate', tpl.id, null, tpl);
  res.json(tpl);
});

router.put('/:id', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (req, res) => {
  const id = String(req.params.id);
  await prisma.flowNode.deleteMany({ where: { templateId: id } });
  const tpl = await prisma.flowTemplate.update({
    where: { id },
    data: {
      name: req.body.name,
      description: req.body.description,
      active: req.body.active,
      nodes: {
        create: (req.body.nodes || []).map((n: any, i: number) => ({
          key: n.key || `NODE_${i + 1}`,
          name: n.name,
          type: n.type || 'CUSTOM',
          sort: n.sort != null ? n.sort : i,
          required: n.required !== false,
          skippable: !!n.skippable,
          role: n.role,
          slaHours: n.slaHours,
          escalateRole: n.escalateRole,
        })),
      },
    },
    include: { nodes: { orderBy: { sort: 'asc' } } },
  });
  res.json(tpl);
});

router.post('/assign/:jobId', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const tpl = await prisma.flowTemplate.findUnique({
    where: { id: req.body.flowTemplateId },
    include: { nodes: { orderBy: { sort: 'asc' } } },
  });
  if (!tpl) return res.status(404).json({ message: '流程模板不存在' });
  const first = tpl.nodes[0];
  const job = await prisma.job.update({
    where: { id: String(req.params.jobId) },
    data: {
      flowTemplateId: tpl.id,
      flowConfig: tpl.nodes.map((n) => n.key).join(','),
    },
  });
  res.json({ job, firstNode: first });
});

router.get('/sla-rules', authRequired, async (_req, res) => {
  res.json(await prisma.slaRule.findMany({ where: { active: true } }));
});

router.post('/sla-rules', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (req, res) => {
  const item = await prisma.slaRule.create({
    data: {
      name: req.body.name,
      scope: req.body.scope || 'GLOBAL',
      scopeRef: req.body.scopeRef,
      nodeKey: req.body.nodeKey,
      hours: Number(req.body.hours),
      warnHours: req.body.warnHours != null ? Number(req.body.warnHours) : null,
      escalateRole: req.body.escalateRole,
    },
  });
  res.json(item);
});

router.post('/check-sla', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD', 'HR'), async (_req, res) => {
  const now = new Date();
  const stalled = await prisma.application.findMany({
    where: {
      status: { in: ['HR_SCREEN', 'DEPT_SCREEN', 'INTERVIEW', 'OFFER', 'ONBOARDING'] },
      slaDueAt: { lt: now },
    },
    include: { candidate: true, job: true },
  });
  const created = [];
  for (const a of stalled) {
    if (!a.slaWarned) {
      await prisma.application.update({ where: { id: a.id }, data: { slaWarned: true } });
    }
    const alert = await prisma.alertEvent.create({
      data: {
        type: 'STALL',
        title: `候选人停滞：${a.candidate.name} - ${a.job.title}`,
        detail: `当前状态 ${a.status}，SLA 已逾期`,
        refType: 'Application',
        refId: a.id,
        level: 'WARN',
      },
    });
    created.push(alert);
    if (a.job.hrOwnerId) {
      await createTodo({
        userId: a.job.hrOwnerId,
        type: 'SCREEN',
        title: `SLA逾期催办：${a.candidate.name}`,
        refType: 'Application',
        refId: a.id,
      });
    }
  }

  const evalTimeout = await prisma.interview.findMany({
    where: { status: 'COMPLETED', endTime: { lt: new Date(Date.now() - 24 * 3600000) } },
    include: { evaluations: true, interviewers: true, application: { include: { candidate: true } } },
  });
  for (const iv of evalTimeout) {
    for (const it of iv.interviewers) {
      const submitted = iv.evaluations.some((e) => e.interviewerId === it.userId && e.status === 'SUBMITTED');
      if (!submitted) {
        created.push(
          await prisma.alertEvent.create({
            data: {
              type: 'EVAL_TIMEOUT',
              title: `评价超时：${iv.application.candidate.name}`,
              refType: 'Interview',
              refId: iv.id,
            },
          })
        );
      }
    }
  }

  await emitBusinessEvent('SLA_CHECKED', 'System', 'sla', { alerts: created.length });
  res.json({ alerts: created.length, items: created });
});

router.get('/alerts', authRequired, async (req, res) => {
  const list = await prisma.alertEvent.findMany({
    where: req.query.resolved === 'true' ? undefined : { resolved: false },
    orderBy: { createdAt: 'desc' },
    take: 100,
  });
  res.json(list);
});

router.post('/alerts/:id/resolve', authRequired, async (req, res) => {
  const item = await prisma.alertEvent.update({
    where: { id: String(req.params.id) },
    data: { resolved: true },
  });
  res.json(item);
});

router.get('/alert-subscriptions', authRequired, async (req, res) => {
  res.json(await prisma.alertSubscription.findMany({ where: { userId: req.user!.id } }));
});

router.post('/alert-subscriptions', authRequired, async (req, res) => {
  const item = await prisma.alertSubscription.create({
    data: {
      userId: req.user!.id,
      alertType: req.body.alertType,
      channel: req.body.channel || 'INAPP',
    },
  });
  res.json(item);
});

export default router;
