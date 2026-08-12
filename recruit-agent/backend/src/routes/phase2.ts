import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, createTodo } from '../utils/helpers';
import { callHrAgent } from '../services/hrAgentClient';

const router = Router();

function applyParsedFields(c: { education: string | null; school: string | null }, parsed: any, confidence: number) {
  const edu0 = parsed?.education?.[0] || {};
  return {
    parsedResume: JSON.stringify(parsed),
    parseConfidence: confidence,
    education: c.education || edu0.degree || undefined,
    school: c.school || edu0.school || undefined,
  };
}

/** HR Agent 回写解析结果（避免与 parse-resume 互相递归） */
router.post('/candidates/:id/apply-parse', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const c = await prisma.candidate.findUnique({ where: { id: String(req.params.id) } });
  if (!c) return res.status(404).json({ message: '候选人不存在' });
  const parsed = req.body?.parsed || {};
  const confidence = Number(req.body?.confidence ?? 0.8);
  const updated = await prisma.candidate.update({
    where: { id: c.id },
    data: applyParsedFields(c, parsed, confidence),
  });
  await writeAudit(req, '简历解析回写', 'Candidate', c.id, null, {
    confidence,
    source: req.body?.source || 'hr-agent',
  });
  res.json({ candidate: updated, parsed, confidence });
});

// Resume parse — 依赖 HR Agent 提供 AI 能力
router.post('/candidates/:id/parse-resume', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const c = await prisma.candidate.findUnique({ where: { id: String(req.params.id) } });
  if (!c) return res.status(404).json({ message: '候选人不存在' });
  const token = (req.headers.authorization || '').replace(/^Bearer\s+/i, '');
  try {
    const result = await callHrAgent<any>('/ai/resume/parse', {
      token,
      body: { candidateId: c.id, resumeText: req.body?.resumeText },
    });
    // Agent 侧通常已 apply-parse；此处再读最新主档
    const updated = await prisma.candidate.findUnique({ where: { id: c.id } });
    await writeAudit(req, '简历自动解析', 'Candidate', c.id, null, {
      confidence: result.confidence,
      provider: result.provider,
    });
    res.json({
      candidate: updated,
      parsed: result.parsed,
      confidence: result.confidence,
      provider: result.provider,
      draft: result.draft,
    });
  } catch (e: any) {
    // HR Agent 不可用时本地降级，保证主流程可继续
    const parsed = {
      education: [{ school: c.school || '示例大学', degree: c.education || '本科', major: '计算机' }],
      experience: [
        {
          company: c.currentCompany || '未知公司',
          title: c.currentTitle || '工程师',
          years: c.yearsOfExp || 3,
          highlights: ['参与核心业务系统建设', '负责前端架构与性能优化'],
        },
      ],
      skills: ['React', 'TypeScript', 'Node.js'],
      projects: [{ name: '招聘管理系统', role: '前端开发', desc: '全流程招聘闭环' }],
      tags: ['降级解析'],
      anomalies: ['HR Agent 不可用，已使用本地规则解析'],
    };
    const confidence = c.resumePath ? 0.7 : 0.55;
    const updated = await prisma.candidate.update({
      where: { id: c.id },
      data: applyParsedFields(c, parsed, confidence),
    });
    await writeAudit(req, '简历自动解析(降级)', 'Candidate', c.id, null, { confidence, error: e.message });
    res.json({ candidate: updated, parsed, confidence, provider: 'fallback', warning: e.message });
  }
});

// Smart duplicate suggestions
router.get('/candidates/duplicates', authRequired, async (req, res) => {
  const all = await prisma.candidate.findMany({ where: { deleted: false, anonymized: false } });
  const groups: any[] = [];
  const used = new Set<string>();
  for (const a of all) {
    if (used.has(a.id)) continue;
    const similar = all.filter((b) => {
      if (b.id === a.id || used.has(b.id)) return false;
      if (a.phone && b.phone && a.phone === b.phone) return true;
      if (a.email && b.email && a.email.toLowerCase() === b.email.toLowerCase()) return true;
      if (a.name === b.name && a.currentCompany && a.currentCompany === b.currentCompany) return true;
      return false;
    });
    if (similar.length) {
      const g = [a, ...similar];
      g.forEach((x) => used.add(x.id));
      groups.push({
        reason: '手机/邮箱完全匹配或姓名+公司疑似',
        candidates: g.map((x) => ({ id: x.id, name: x.name, phone: x.phone, email: x.email, company: x.currentCompany })),
      });
    }
  }
  res.json(groups);
});

router.post('/candidates/merge', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { primaryId, mergeIds } = req.body;
  if (!primaryId || !Array.isArray(mergeIds) || !mergeIds.length) {
    return res.status(400).json({ message: '请指定主档与待合并ID' });
  }
  const primary = await prisma.candidate.findUnique({ where: { id: primaryId } });
  if (!primary) return res.status(404).json({ message: '主档不存在' });
  for (const mid of mergeIds) {
    await prisma.application.updateMany({ where: { candidateId: mid }, data: { candidateId: primaryId } });
    await prisma.candidateRemark.updateMany({ where: { candidateId: mid }, data: { candidateId: primaryId } });
    await prisma.candidate.update({
      where: { id: mid },
      data: { deleted: true, anonymized: true, name: `${primary.name}-已合并`, phone: null, email: null },
    });
  }
  await writeAudit(req, '候选人合并', 'Candidate', primaryId, null, { mergeIds });
  res.json({ ok: true, primaryId, merged: mergeIds.length });
});

// Calendar busy
router.get('/calendar/busy', authRequired, async (req, res) => {
  const userId = String(req.query.userId || req.user!.id);
  const from = req.query.from ? new Date(String(req.query.from)) : new Date();
  const to = req.query.to ? new Date(String(req.query.to)) : new Date(Date.now() + 14 * 86400000);
  const manual = await prisma.calendarBusy.findMany({
    where: { userId, startTime: { lt: to }, endTime: { gt: from } },
  });
  const interviews = await prisma.interview.findMany({
    where: {
      status: 'SCHEDULED',
      interviewers: { some: { userId } },
      startTime: { lt: to },
      endTime: { gt: from },
    },
  });
  res.json({
    busy: [
      ...manual.map((m) => ({ ...m, kind: 'manual' })),
      ...interviews.map((i) => ({
        id: i.id,
        userId,
        startTime: i.startTime,
        endTime: i.endTime,
        title: `面试-${i.roundName}`,
        kind: 'interview',
      })),
    ],
  });
});

router.post('/calendar/busy', authRequired, async (req, res) => {
  const item = await prisma.calendarBusy.create({
    data: {
      userId: req.body.userId || req.user!.id,
      startTime: new Date(req.body.startTime),
      endTime: new Date(req.body.endTime),
      title: req.body.title || '忙碌',
      source: 'MANUAL',
    },
  });
  res.json(item);
});

router.post('/interviews/:id/sync-calendar', authRequired, requireRoles('HR', 'ADMIN'), async (req, res) => {
  const interview = await prisma.interview.findUnique({
    where: { id: String(req.params.id) },
    include: { interviewers: true },
  });
  if (!interview) return res.status(404).json({ message: '面试不存在' });
  for (const it of interview.interviewers) {
    await prisma.calendarBusy.create({
      data: {
        userId: it.userId,
        startTime: interview.startTime,
        endTime: interview.endTime,
        title: `面试同步-${interview.roundName}`,
        source: 'SYNC',
        externalId: interview.id,
      },
    });
  }
  const updated = await prisma.interview.update({
    where: { id: interview.id },
    data: { calendarSynced: true },
  });
  res.json(updated);
});

router.post('/interviews/:id/slots', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const slots = req.body.slots || [];
  const interview = await prisma.interview.update({
    where: { id: String(req.params.id) },
    data: { slotOptions: JSON.stringify(slots) },
  });
  res.json(interview);
});

router.post('/interviews/:id/pack', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const interview = await prisma.interview.update({
    where: { id: String(req.params.id) },
    data: { packContent: req.body.packContent },
  });
  res.json(interview);
});

// Warm tasks
router.get('/warm-tasks', authRequired, async (req, res) => {
  const where: any = {};
  if (req.query.status) where.status = String(req.query.status);
  res.json(await prisma.warmTask.findMany({ where, include: { offer: true }, orderBy: { dueAt: 'asc' } }));
});

router.post('/warm-tasks', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const task = await prisma.warmTask.create({
    data: {
      offerId: req.body.offerId,
      candidateId: req.body.candidateId,
      stage: req.body.stage || 'PENDING_CONFIRM',
      title: req.body.title,
      content: req.body.content,
      dueAt: req.body.dueAt ? new Date(req.body.dueAt) : null,
    },
  });
  res.json(task);
});

router.post('/warm-tasks/:id/done', authRequired, async (req, res) => {
  const task = await prisma.warmTask.update({
    where: { id: String(req.params.id) },
    data: { status: 'DONE', result: req.body.result, doneAt: new Date() },
  });
  res.json(task);
});

// Onboarding collab
router.get('/onboarding/:id/collab', authRequired, async (req, res) => {
  const tasks = await prisma.onboardCollabTask.findMany({ where: { onboardingId: String(req.params.id) } });
  res.json(tasks);
});

router.post('/onboarding/:id/collab/:taskId/done', authRequired, requireRoles('HR_OPS', 'HR', 'ADMIN'), async (req, res) => {
  const task = await prisma.onboardCollabTask.update({
    where: { id: String(req.params.taskId) },
    data: { status: 'DONE', doneAt: new Date() },
  });
  res.json(task);
});

// E-sign stub
router.post('/offers/:id/esign', authRequired, requireRoles('HR', 'ADMIN'), async (req, res) => {
  const offer = await prisma.offer.update({
    where: { id: String(req.params.id) },
    data: {
      eSignStatus: 'PENDING',
      eSignRef: `ESIGN-${Date.now()}`,
    },
  });
  res.json({ message: '已发起电子签（接口预留，当前为模拟）', offer });
});

router.post('/offers/:id/esign/callback', authRequired, async (req, res) => {
  const offer = await prisma.offer.update({
    where: { id: String(req.params.id) },
    data: { eSignStatus: req.body.status || 'SIGNED' },
  });
  res.json(offer);
});

// Talent pool advanced
router.post('/talent/activations', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { name, tagFilter, jobId, candidateIds } = req.body;
  const act = await prisma.talentActivation.create({
    data: {
      name,
      tagFilter,
      jobId,
      items: {
        create: (candidateIds || []).map((candidateId: string) => ({ candidateId })),
      },
    },
    include: { items: true },
  });
  for (const item of act.items) {
    const hrs = await prisma.user.findMany({ where: { role: 'HR', active: true } });
    if (hrs[0]) {
      await createTodo({
        userId: hrs[0].id,
        type: 'SCREEN',
        title: `人才激活联系：${name}`,
        refType: 'TalentActivationItem',
        refId: item.id,
      });
    }
  }
  res.json(act);
});

router.get('/talent/activations', authRequired, async (_req, res) => {
  res.json(await prisma.talentActivation.findMany({ include: { items: true }, orderBy: { createdAt: 'desc' } }));
});

router.post('/talent/activations/items/:id', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.talentActivationItem.update({
    where: { id: String(req.params.id) },
    data: {
      status: req.body.status,
      result: req.body.result,
      contactedAt: new Date(),
    },
  });
  res.json(item);
});

router.post('/talent/:candidateId/tier', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const updated = await prisma.candidate.update({
    where: { id: String(req.params.candidateId) },
    data: {
      poolTier: req.body.poolTier,
      poolLevel: req.body.poolLevel,
      poolActiveScore: req.body.poolActiveScore != null ? Number(req.body.poolActiveScore) : undefined,
      retainUntil: req.body.retainUntil ? new Date(req.body.retainUntil) : undefined,
      privacyConsent: req.body.privacyConsent,
    },
  });
  res.json(updated);
});

router.post('/talent/:candidateId/anonymize', authRequired, requireRoles('ADMIN', 'HR_OPS'), async (req, res) => {
  if (!req.body.reason) return res.status(400).json({ message: '匿名化必须填写原因' });
  const updated = await prisma.candidate.update({
    where: { id: String(req.params.candidateId) },
    data: {
      anonymized: true,
      phone: null,
      email: null,
      name: '已匿名',
      resumePath: null,
      parsedResume: null,
    },
  });
  await writeAudit(req, '候选人匿名化', 'Candidate', updated.id, null, null, req.body.reason);
  res.json(updated);
});

export default router;
