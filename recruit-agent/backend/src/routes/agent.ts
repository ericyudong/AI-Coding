import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, createTodo, addProcessEvent, emitBusinessEvent, maskSensitive } from '../utils/helpers';
import { executeChannelPublish, executeExternalOutreach } from '../channels/service';
import { compliance } from '../config/compliance';

const router = Router();

const HIGH_RISK = new Set([
  'REJECT_CANDIDATE',
  'SEND_OFFER',
  'WITHDRAW_OFFER',
  'DELETE_PERSONAL_DATA',
  'SEND_EXTERNAL_MESSAGE',
  'PUBLISH_CHANNEL',
  'EXTERNAL_OUTREACH',
]);

async function resolveInitiator(req: any) {
  return req.user;
}

function filterByScope(data: any, role: string) {
  if (role === 'DATA_VIEWER' || role === 'INTERVIEWER') return maskSensitive(data);
  return data;
}

// P2-AGT-006 semantic dictionary
router.get('/semantics', authRequired, async (_req, res) => {
  const list = await prisma.semanticDict.findMany({ orderBy: [{ category: 'asc' }, { key: 'asc' }] });
  res.json(list);
});

// P2-AGT-002 structured query
router.get('/query/:objectType/:id', authRequired, async (req, res) => {
  const { objectType, id } = req.params;
  const role = req.user!.role;
  let data: any = null;
  switch (objectType) {
    case 'job':
      data = await prisma.job.findUnique({
        where: { id: String(id) },
        include: { org: true, request: true, applications: { take: 20, include: { candidate: true } } },
      });
      break;
    case 'candidate':
      data = await prisma.candidate.findUnique({
        where: { id: String(id) },
        include: { applications: { include: { job: true, interviews: { include: { evaluations: true } }, offers: true } } },
      });
      break;
    case 'application':
      data = await prisma.application.findUnique({
        where: { id: String(id) },
        include: { candidate: true, job: true, events: true, interviews: { include: { evaluations: true } }, offers: true },
      });
      break;
    case 'offer':
      data = await prisma.offer.findUnique({
        where: { id: String(id) },
        include: { application: { include: { candidate: true, job: true } } },
      });
      break;
    default:
      return res.status(400).json({ message: '不支持的对象类型' });
  }
  if (!data) return res.status(404).json({ message: '对象不存在' });
  await writeAudit(req, 'Agent结构化查询', objectType, String(id));
  res.json(filterByScope(data, role));
});

router.get('/search', authRequired, async (req, res) => {
  const { q, type } = req.query;
  if (!q) return res.status(400).json({ message: '请提供关键词 q' });
  const keyword = String(q);
  const result: any = {};
  if (!type || type === 'job') {
    result.jobs = await prisma.job.findMany({
      where: { OR: [{ title: { contains: keyword } }, { workLocation: { contains: keyword } }] },
      take: 20,
    });
  }
  if (!type || type === 'candidate') {
    let cands = await prisma.candidate.findMany({
      where: {
        deleted: false,
        OR: [{ name: { contains: keyword } }, { phone: { contains: keyword } }, { email: { contains: keyword } }],
      },
      take: 20,
    });
    if (req.user!.role === 'DATA_VIEWER') cands = cands.map((c) => maskSensitive(c));
    result.candidates = cands;
  }
  if (!type || type === 'application') {
    result.applications = await prisma.application.findMany({
      where: { candidate: { name: { contains: keyword } } },
      include: { candidate: true, job: true },
      take: 20,
    });
  }
  res.json(result);
});

// P2-AGT-003 drafts
router.post('/drafts', authRequired, async (req, res) => {
  const { type, content, refType, refId, agentId } = req.body;
  if (!type || !content) return res.status(400).json({ message: '草稿类型与内容必填' });
  const draft = await prisma.agentDraft.create({
    data: {
      type,
      content: typeof content === 'string' ? content : JSON.stringify(content),
      refType,
      refId,
      agentId: agentId || 'hr-agent',
      initiatorId: req.user!.id,
      sourceTag: 'AI_GENERATED',
      status: 'DRAFT',
    },
  });
  await writeAudit(req, 'Agent创建草稿', 'AgentDraft', draft.id, null, { type, sourceTag: 'AI_GENERATED' });
  res.json(draft);
});

router.get('/drafts', authRequired, async (req, res) => {
  const where: any = {};
  if (req.query.type) where.type = String(req.query.type);
  if (req.query.status) where.status = String(req.query.status);
  res.json(await prisma.agentDraft.findMany({ where, orderBy: { createdAt: 'desc' }, take: 100 }));
});

router.post('/drafts/:id/accept', authRequired, async (req, res) => {
  const draft = await prisma.agentDraft.update({
    where: { id: String(req.params.id) },
    data: { status: 'ACCEPTED', content: req.body.content || undefined },
  });
  res.json(draft);
});

// P2-AGT-004 / 007 / 008 / 009 actions with confirmation
router.post('/actions', authRequired, async (req, res) => {
  const { actionKey, payload, agentId, idempotencyKey, autoConfirm } = req.body;
  if (!actionKey) return res.status(400).json({ message: 'actionKey 必填' });

  if (idempotencyKey) {
    const existing = await prisma.agentAction.findUnique({ where: { idempotencyKey } });
    if (existing) return res.json({ reused: true, action: existing });
  }

  const riskLevel = HIGH_RISK.has(actionKey) ? 'HIGH' : actionKey.startsWith('DRAFT_') ? 'DRAFT' : actionKey.startsWith('READ_') ? 'READ' : 'LOW';
  const action = await prisma.agentAction.create({
    data: {
      actionKey,
      riskLevel,
      payload: JSON.stringify(payload || {}),
      agentId: agentId || 'hr-agent',
      initiatorId: req.user!.id,
      status: riskLevel === 'HIGH' && !autoConfirm ? 'PENDING' : 'CONFIRMED',
      idempotencyKey: idempotencyKey || null,
      confirmUserId: riskLevel === 'HIGH' && !autoConfirm ? null : req.user!.id,
      confirmedAt: riskLevel === 'HIGH' && !autoConfirm ? null : new Date(),
    },
  });

  await writeAudit(req, 'Agent发起动作', 'AgentAction', action.id, null, { actionKey, riskLevel });

  if (action.status === 'PENDING') {
    return res.status(202).json({
      message: '高风险动作需人工确认后执行',
      action,
      confirmUrl: `/api/agent/actions/${action.id}/confirm`,
    });
  }

  try {
    const result = await executeAction(action.id, req);
    res.json(result);
  } catch (e: any) {
    res.status(400).json({ message: e.message, actionId: action.id });
  }
});

router.post('/actions/:id/confirm', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN', 'OFFER_APPROVER'), async (req, res) => {
  const action = await prisma.agentAction.findUnique({ where: { id: String(req.params.id) } });
  if (!action) return res.status(404).json({ message: '动作不存在' });
  if (action.status !== 'PENDING') return res.status(400).json({ message: '当前状态不可确认' });
  if (req.body.reject) {
    const updated = await prisma.agentAction.update({
      where: { id: action.id },
      data: { status: 'REJECTED', confirmUserId: req.user!.id, confirmedAt: new Date(), result: req.body.reason || '人工拒绝' },
    });
    return res.json(updated);
  }
  await prisma.agentAction.update({
    where: { id: action.id },
    data: { status: 'CONFIRMED', confirmUserId: req.user!.id, confirmedAt: new Date() },
  });
  try {
    const result = await executeAction(action.id, req);
    res.json(result);
  } catch (e: any) {
    res.status(400).json({ message: e.message });
  }
});

router.get('/actions', authRequired, async (req, res) => {
  const where: any = {};
  if (req.query.status) where.status = String(req.query.status);
  res.json(await prisma.agentAction.findMany({ where, orderBy: { createdAt: 'desc' }, take: 100 }));
});

router.get('/actions/:id', authRequired, async (req, res) => {
  const action = await prisma.agentAction.findUnique({ where: { id: String(req.params.id) } });
  if (!action) return res.status(404).json({ message: '不存在' });
  res.json(action);
});

// P2-AGT-005 events
router.get('/events', authRequired, async (req, res) => {
  const where: any = {};
  if (req.query.eventType) where.eventType = String(req.query.eventType);
  if (req.query.objectType) where.objectType = String(req.query.objectType);
  const since = req.query.since ? new Date(String(req.query.since)) : undefined;
  if (since) where.createdAt = { gte: since };
  res.json(await prisma.businessEvent.findMany({ where, orderBy: { createdAt: 'desc' }, take: 200 }));
});

router.post('/event-subscriptions', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const sub = await prisma.eventSubscription.create({
    data: {
      name: req.body.name,
      eventTypes: Array.isArray(req.body.eventTypes) ? req.body.eventTypes.join(',') : req.body.eventTypes,
      callbackUrl: req.body.callbackUrl,
    },
  });
  res.json(sub);
});

async function executeAction(actionId: string, req: any) {
  const action = await prisma.agentAction.findUnique({ where: { id: actionId } });
  if (!action) throw new Error('动作不存在');
  if (!['CONFIRMED', 'PENDING'].includes(action.status) && action.status !== 'CONFIRMED') {
    // already handled
  }
  if (action.status === 'EXECUTED') return { reused: true, action };

  const payload = JSON.parse(action.payload || '{}');
  let result: any = { ok: true };

  switch (action.actionKey) {
    case 'CREATE_CANDIDATE': {
      if (!payload.name || (!payload.phone && !payload.email)) throw new Error('候选人信息不完整');
      const c = await prisma.candidate.create({
        data: {
          name: payload.name,
          phone: payload.phone,
          email: payload.email,
          source: payload.source || 'Agent创建',
          currentCompany: payload.currentCompany,
          currentTitle: payload.currentTitle,
        },
      });
      result = { candidateId: c.id };
      break;
    }
    case 'LINK_JOB': {
      const app = await prisma.application.create({
        data: { candidateId: payload.candidateId, jobId: payload.jobId, status: 'HR_SCREEN', stage: 'HR_SCREEN' },
      });
      await addProcessEvent({
        applicationId: app.id,
        type: 'ENTER',
        toStatus: 'HR_SCREEN',
        operatorId: req.user.id,
        operatorName: `Agent/${req.user.name}`,
        detail: 'Agent动作关联职位',
      });
      result = { applicationId: app.id };
      break;
    }
    case 'CREATE_INTERVIEW': {
      if (!payload.applicationId || !payload.startTime || !payload.endTime || !payload.interviewerIds?.length) {
        throw new Error('面试参数不完整');
      }
      const interview = await prisma.interview.create({
        data: {
          applicationId: payload.applicationId,
          round: payload.round || 'FIRST',
          roundName: payload.roundName || '初试',
          startTime: new Date(payload.startTime),
          endTime: new Date(payload.endTime),
          method: payload.method || 'VIDEO',
          meetingLink: payload.meetingLink,
          location: payload.location,
          status: 'SCHEDULED',
          interviewers: { create: payload.interviewerIds.map((userId: string) => ({ userId })) },
        },
      });
      result = { interviewId: interview.id };
      break;
    }
    case 'ADD_TALENT_POOL': {
      await prisma.candidate.update({
        where: { id: payload.candidateId },
        data: { inTalentPool: true, poolRemark: payload.reason, poolTier: payload.poolTier || 'GENERAL' },
      });
      result = { candidateId: payload.candidateId };
      break;
    }
    case 'ADVANCE_NODE': {
      const app = await prisma.application.update({
        where: { id: payload.applicationId },
        data: { status: payload.toStatus, stage: payload.toStatus },
      });
      await addProcessEvent({
        applicationId: app.id,
        type: 'ADVANCE',
        fromStatus: payload.fromStatus,
        toStatus: payload.toStatus,
        operatorId: req.user.id,
        operatorName: `Agent/${req.user.name}`,
        reason: payload.reason,
      });
      result = { applicationId: app.id, status: app.status };
      break;
    }
    case 'REJECT_CANDIDATE': {
      const app = await prisma.application.update({
        where: { id: payload.applicationId },
        data: { status: 'REJECTED', rejectReason: payload.reason || '不匹配', rejectToPool: !!payload.toPool },
      });
      if (payload.toPool) {
        const a = await prisma.application.findUnique({ where: { id: app.id } });
        if (a) await prisma.candidate.update({ where: { id: a.candidateId }, data: { inTalentPool: true, poolRemark: payload.reason } });
      }
      await addProcessEvent({
        applicationId: app.id,
        type: 'REJECT',
        toStatus: 'REJECTED',
        operatorId: req.user.id,
        operatorName: `Agent/${req.user.name}`,
        reason: payload.reason,
      });
      result = { applicationId: app.id };
      break;
    }
    case 'SEND_OFFER': {
      const offer = await prisma.offer.update({
        where: { id: payload.offerId },
        data: { status: 'SENT', sentAt: new Date(), sentBy: req.user.id },
      });
      result = { offerId: offer.id };
      break;
    }
    case 'WITHDRAW_OFFER': {
      const offer = await prisma.offer.update({
        where: { id: payload.offerId },
        data: { status: 'WITHDRAWN', withdrawReason: payload.reason || '撤回', isActive: false },
      });
      result = { offerId: offer.id };
      break;
    }
    case 'CREATE_TODO': {
      const todo = await createTodo({
        userId: payload.userId,
        type: payload.type || 'SCREEN',
        title: payload.title,
        refType: payload.refType,
        refId: payload.refId,
      });
      result = { todoId: todo.id };
      break;
    }
    case 'ADD_TAG': {
      const c = await prisma.candidate.findUnique({ where: { id: payload.candidateId } });
      if (!c) throw new Error('候选人不存在');
      const tags = new Set((c.tags || '').split(',').filter(Boolean));
      tags.add(payload.tag);
      await prisma.candidate.update({ where: { id: c.id }, data: { tags: [...tags].join(',') } });
      result = { tags: [...tags] };
      break;
    }
    case 'PUBLISH_CHANNEL': {
      if (!payload.jobId || !payload.channelId) throw new Error('发布参数不完整');
      const pubResult = await executeChannelPublish({
        jobId: payload.jobId,
        channelId: payload.channelId,
        operatorName: req.user.name,
      });
      await emitBusinessEvent('JOB_CHANNEL_PUBLISH', 'Job', payload.jobId, {
        channelId: payload.channelId,
        status: pubResult.publish.status,
        mode: pubResult.mode,
        via: 'AgentAction',
      });
      if (!pubResult.adapterResult.ok) throw new Error(pubResult.adapterResult.message);
      result = pubResult;
      break;
    }
    case 'EXTERNAL_OUTREACH': {
      if (!payload.jobId || !payload.candidateId || !payload.message || !payload.channelCode) {
        throw new Error('外部触达参数不完整');
      }
      if (compliance.mode === 'live' && !compliance.externalOutreachEnabled) {
        throw new Error('合规拦截：EXTERNAL_OUTREACH_ENABLED 未开启');
      }
      const outreach = await executeExternalOutreach({
        channelCode: payload.channelCode,
        jobId: payload.jobId,
        candidateId: payload.candidateId,
        message: payload.message,
        externalCandidateRef: payload.externalCandidateRef,
        operatorName: req.user.name,
      });
      await emitBusinessEvent('EXTERNAL_OUTREACH', 'Candidate', payload.candidateId, {
        jobId: payload.jobId,
        channelCode: payload.channelCode,
        mode: outreach.mode,
        ok: outreach.adapterResult.ok,
      });
      if (!outreach.adapterResult.ok) throw new Error(outreach.adapterResult.message);
      result = outreach;
      break;
    }
    default:
      throw new Error(`未知或不允许的动作: ${action.actionKey}`);
  }

  const updated = await prisma.agentAction.update({
    where: { id: action.id },
    data: { status: 'EXECUTED', result: JSON.stringify(result), executedAt: new Date() },
  });
  await emitBusinessEvent('AGENT_ACTION_EXECUTED', 'AgentAction', action.id, { actionKey: action.actionKey, result });
  await writeAudit(req, 'Agent动作已执行', 'AgentAction', action.id, null, result);
  return { action: updated, result };
}

export default router;
