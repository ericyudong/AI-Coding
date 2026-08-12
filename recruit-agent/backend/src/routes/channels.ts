import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, emitBusinessEvent, createTodo } from '../utils/helpers';
import { compliance, complianceSnapshot } from '../config/compliance';
import { adaptersHealth, listChannelAdapters } from '../channels/registry';
import { executeChannelPublish } from '../channels/service';

const router = Router();

router.get('/compliance', authRequired, async (_req, res) => {
  res.json(complianceSnapshot());
});

router.get('/adapters', authRequired, async (_req, res) => {
  const health = await adaptersHealth();
  res.json({ adapters: listChannelAdapters(), health, mode: compliance.mode });
});

router.get('/publishes', authRequired, async (req, res) => {
  const where: any = {};
  if (req.query.jobId) where.jobId = String(req.query.jobId);
  const list = await prisma.jobChannelPublish.findMany({
    where,
    include: { channel: true, job: { select: { id: true, title: true, status: true } } },
    orderBy: { updatedAt: 'desc' },
  });
  res.json(list);
});

router.get('/', authRequired, async (_req, res) => {
  const list = await prisma.channel.findMany({
    include: { accounts: true, _count: { select: { publishes: true } } },
    orderBy: { name: 'asc' },
  });
  res.json(list);
});

router.post('/', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (req, res) => {
  const item = await prisma.channel.create({
    data: {
      name: req.body.name,
      code: String(req.body.code || '').toUpperCase(),
      type: req.body.type || 'SITE',
      accounts: req.body.accountName
        ? {
            create: [
              {
                accountName: req.body.accountName,
                externalId: req.body.externalId,
                mappingJson: req.body.mappingJson,
              },
            ],
          }
        : undefined,
    },
    include: { accounts: true },
  });
  res.json(item);
});

/**
 * 发布入口：默认进入人工审核闸门（AgentAction PUBLISH_CHANNEL）
 */
router.post('/publish', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { jobId, channelId, bypassConfirm } = req.body;
  const job = await prisma.job.findUnique({ where: { id: jobId } });
  const channel = await prisma.channel.findUnique({ where: { id: channelId } });
  if (!job || !channel) return res.status(404).json({ message: '职位或渠道不存在' });
  if (job.status !== 'OPEN') return res.status(400).json({ message: '仅招聘中职位可对外发布' });

  const needConfirm =
    compliance.requireHumanConfirm &&
    !(bypassConfirm && req.user!.role === 'ADMIN' && compliance.mode === 'sandbox');

  if (needConfirm) {
    const action = await prisma.agentAction.create({
      data: {
        actionKey: 'PUBLISH_CHANNEL',
        riskLevel: 'HIGH',
        payload: JSON.stringify({ jobId, channelId, channelCode: channel.code, jobTitle: job.title }),
        agentId: 'channel-gateway',
        initiatorId: req.user!.id,
        status: 'PENDING',
        idempotencyKey: `publish-${jobId}-${channelId}-${Date.now()}`,
      },
    });
    await createTodo({
      userId: req.user!.id,
      type: 'APPROVE_REQUEST',
      title: `待确认渠道发布：${job.title} → ${channel.name}`,
      refType: 'AgentAction',
      refId: action.id,
    });
    await writeAudit(req, '渠道发布待确认', 'AgentAction', action.id, null, { jobId, channelId });
    return res.status(202).json({
      message: '外部渠道发布为高风险动作，已提交人工确认闸门',
      action,
      confirmUrl: `/api/agent/actions/${action.id}/confirm`,
      compliance: complianceSnapshot(),
    });
  }

  try {
    const result = await executeChannelPublish({
      jobId,
      channelId,
      operatorName: req.user!.name,
    });
    await writeAudit(req, '职位渠道发布', 'JobChannelPublish', result.publish.id, null, result);
    await emitBusinessEvent('JOB_CHANNEL_PUBLISH', 'Job', jobId, {
      channelId,
      status: result.publish.status,
      mode: result.mode,
    });
    if (!result.adapterResult.ok) {
      return res.status(502).json({ message: result.adapterResult.message, ...result });
    }
    res.json(result);
  } catch (e: any) {
    res.status(400).json({ message: e.message });
  }
});

router.post('/publishes/:id/status', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { status } = req.body;
  if (!['PUBLISHED', 'PAUSED', 'CLOSED'].includes(status)) return res.status(400).json({ message: '无效状态' });
  const pub = await prisma.jobChannelPublish.update({
    where: { id: String(req.params.id) },
    data: { status, resultMsg: `状态更新为 ${status}` },
  });
  res.json(pub);
});

/** 批量提交外部打招呼到人工审核闸门 */
router.post('/outreach/submit', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { jobId, channelCode, items } = req.body || {};
  if (!jobId || !channelCode || !Array.isArray(items) || !items.length) {
    return res.status(400).json({ message: 'jobId、channelCode、items 必填' });
  }
  if (compliance.mode === 'live' && !compliance.externalOutreachEnabled) {
    return res.status(403).json({
      message: '合规拦截：外部触达总开关未开启（EXTERNAL_OUTREACH_ENABLED）',
      compliance: complianceSnapshot(),
    });
  }

  const created = [];
  for (const item of items.slice(0, 30)) {
    if (!item.candidateId || !item.message) continue;
    const action = await prisma.agentAction.create({
      data: {
        actionKey: 'EXTERNAL_OUTREACH',
        riskLevel: 'HIGH',
        payload: JSON.stringify({
          jobId,
          channelCode: String(channelCode).toUpperCase(),
          candidateId: item.candidateId,
          candidateName: item.candidateName,
          message: item.message,
          externalCandidateRef: item.externalCandidateRef,
        }),
        agentId: 'hr-agent',
        initiatorId: req.user!.id,
        status: 'PENDING',
        idempotencyKey: `outreach-${jobId}-${item.candidateId}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      },
    });
    created.push(action);
  }

  if (created.length) {
    await createTodo({
      userId: req.user!.id,
      type: 'SCREEN',
      title: `待确认外部寻访打招呼 ${created.length} 条（${String(channelCode).toUpperCase()}）`,
      refType: 'AgentAction',
      refId: created[0].id,
    });
  }

  await writeAudit(req, '外部触达提交审核', 'AgentAction', created[0]?.id || null, null, {
    count: created.length,
    channelCode,
    jobId,
  });

  res.status(202).json({
    message: `已提交 ${created.length} 条外部触达到人工审核闸门`,
    actions: created,
    compliance: complianceSnapshot(),
  });
});

router.post('/:id/accounts', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (req, res) => {
  const account = await prisma.channelAccount.create({
    data: {
      channelId: String(req.params.id),
      accountName: req.body.accountName,
      externalId: req.body.externalId,
      mappingJson:
        typeof req.body.mappingJson === 'string' ? req.body.mappingJson : JSON.stringify(req.body.mappingJson || {}),
    },
  });
  res.json(account);
});

export default router;
