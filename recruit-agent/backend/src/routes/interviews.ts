import { Router } from 'express';
import dayjs from 'dayjs';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity, createTodo, completeTodos, addProcessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { from, to, interviewerId, status } = req.query;
  const where: Record<string, unknown> = {};
  if (status) where.status = String(status);
  if (from || to) {
    where.startTime = {};
    if (from) (where.startTime as Record<string, Date>).gte = new Date(String(from));
    if (to) (where.startTime as Record<string, Date>).lte = new Date(String(to));
  }
  if (interviewerId) {
    where.interviewers = { some: { userId: String(interviewerId) } };
  }
  const list = await prisma.interview.findMany({
    where,
    include: {
      application: { include: { candidate: true, job: true } },
      interviewers: { include: { user: { select: { id: true, name: true } } } },
      evaluations: true,
    },
    orderBy: { startTime: 'asc' },
  });
  res.json(list);
});

router.get('/:id', authRequired, async (req, res) => {
  const item = await prisma.interview.findUnique({
    where: { id: req.params.id },
    include: {
      application: { include: { candidate: true, job: true } },
      interviewers: { include: { user: { select: { id: true, name: true, email: true } } } },
      evaluations: { include: { interviewer: { select: { id: true, name: true } } } },
    },
  });
  if (!item) return res.status(404).json({ message: '面试不存在' });

  // Hide other evaluations if current user hasn't submitted (interviewer rule)
  const isInterviewer = item.interviewers.some((i) => i.userId === req.user!.id);
  const myEval = item.evaluations.find((e) => e.interviewerId === req.user!.id);
  const canSeeAll =
    ['ADMIN', 'HR', 'RECRUIT_LEAD'].includes(req.user!.role) ||
    (myEval && myEval.status === 'SUBMITTED') ||
    !isInterviewer;

  const evaluations = canSeeAll
    ? item.evaluations
    : item.evaluations.filter((e) => e.interviewerId === req.user!.id);

  res.json({ ...item, evaluations });
});

router.post('/', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const body = req.body;
  if (!body.applicationId || !body.round || !body.startTime || !body.endTime || !body.method) {
    return res.status(400).json({ message: '请填写应聘记录、轮次、时间、面试方式' });
  }
  const start = new Date(body.startTime);
  const end = new Date(body.endTime);
  if (end <= start) return res.status(400).json({ message: '结束时间须晚于开始时间' });
  if (!Array.isArray(body.interviewerIds) || !body.interviewerIds.length) {
    return res.status(400).json({ message: '至少选择1名面试官' });
  }
  if (body.method === 'ONSITE' && !body.location) return res.status(400).json({ message: '线下面试需填写地址' });
  if (body.method === 'VIDEO' && !body.meetingLink) return res.status(400).json({ message: '视频面试需填写会议链接' });

  const app = await prisma.application.findUnique({
    where: { id: body.applicationId },
    include: { candidate: true, job: true },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (!['INTERVIEW', 'DEPT_SCREEN', 'HR_SCREEN'].includes(app.status) && app.status !== 'INTERVIEW') {
    // allow from interview stage primarily
  }

  // conflict check
  const conflicts = [];
  for (const uid of body.interviewerIds) {
    const overlap = await prisma.interview.findFirst({
      where: {
        status: { in: ['SCHEDULED'] },
        interviewers: { some: { userId: uid } },
        startTime: { lt: end },
        endTime: { gt: start },
      },
      include: { interviewers: { include: { user: true } }, application: { include: { candidate: true } } },
    });
    if (overlap) {
      const user = await prisma.user.findUnique({ where: { id: uid } });
      conflicts.push({
        interviewerId: uid,
        interviewerName: user?.name,
        conflictInterviewId: overlap.id,
        time: `${dayjs(overlap.startTime).format('YYYY-MM-DD HH:mm')}-${dayjs(overlap.endTime).format('HH:mm')}`,
      });
    }
  }
  if (conflicts.length && !body.forceConflict) {
    return res.status(409).json({ message: '面试官时间冲突', conflicts });
  }

  const interviewers = await prisma.user.findMany({ where: { id: { in: body.interviewerIds } } });
  const roundLabel =
    body.roundName ||
    ({ FIRST: '初试', SECOND: '复试', FINAL: '终试', CUSTOM: '自定义' }[body.round as string] || body.round);
  const methodLabel = { ONSITE: '线下面试', VIDEO: '在线视频', PHONE: '电话面试' }[body.method as string] || body.method;
  const place =
    body.method === 'ONSITE' ? body.location : body.method === 'VIDEO' ? body.meetingLink : '电话沟通';
  const noticeContent =
    body.noticeContent ||
    `【面试通知】\n候选人：${app.candidate.name}\n职位：${app.job.title}\n轮次：${roundLabel}\n时间：${dayjs(start).format('YYYY-MM-DD HH:mm')} - ${dayjs(end).format('HH:mm')}\n方式：${methodLabel}\n地点/链接：${place}\n面试官：${interviewers.map((u) => u.name).join('、')}\n备注：${body.remark || '无'}`;

  const interview = await prisma.interview.create({
    data: {
      applicationId: app.id,
      round: body.round,
      roundName: roundLabel,
      startTime: start,
      endTime: end,
      method: body.method,
      location: body.location,
      meetingLink: body.meetingLink,
      contactInfo: body.contactInfo,
      remark: body.remark,
      noticeContent,
      status: 'SCHEDULED',
      interviewers: {
        create: body.interviewerIds.map((userId: string) => ({ userId })),
      },
    },
    include: {
      interviewers: { include: { user: true } },
      application: { include: { candidate: true, job: true } },
    },
  });

  if (app.status !== 'INTERVIEW') {
    await prisma.application.update({
      where: { id: app.id },
      data: { status: 'INTERVIEW', stage: 'INTERVIEW' },
    });
  }
  await completeTodos('Application', app.id, 'ARRANGE_INTERVIEW');
  for (const uid of body.interviewerIds) {
    await createTodo({
      userId: uid,
      type: 'EVALUATE',
      title: `待评价：${app.candidate.name} ${roundLabel}（面试结束后提交）`,
      refType: 'Interview',
      refId: interview.id,
      dueAt: end,
    });
  }
  await addProcessEvent({
    applicationId: app.id,
    type: 'INTERVIEW_SCHEDULED',
    fromStatus: app.status,
    toStatus: 'INTERVIEW',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    detail: `${roundLabel} ${dayjs(start).format('YYYY-MM-DD HH:mm')}`,
  });
  await writeAudit(req, '创建面试', 'Interview', interview.id, null, interview);
  await writeActivity({
    type: 'INTERVIEW_SCHEDULED',
    title: `已安排面试：${app.candidate.name} ${roundLabel}`,
    jobId: app.jobId,
    relatedId: interview.id,
    actorId: req.user!.id,
    actorName: req.user!.name,
  });
  res.json(interview);
});

router.post('/:id/notice-sent', authRequired, async (req, res) => {
  const item = await prisma.interview.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  const updated = await prisma.interview.update({
    where: { id: item.id },
    data: { noticeSentAt: new Date(), noticeContent: req.body.noticeContent || item.noticeContent },
  });
  res.json(updated);
});

router.post('/:id/reschedule', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.interview.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  if (!req.body.reason) return res.status(400).json({ message: '改期需填写原因' });
  const start = new Date(req.body.startTime);
  const end = new Date(req.body.endTime);
  if (end <= start) return res.status(400).json({ message: '结束时间须晚于开始时间' });
  const updated = await prisma.interview.update({
    where: { id: item.id },
    data: {
      previousStart: item.startTime,
      previousEnd: item.endTime,
      startTime: start,
      endTime: end,
      rescheduleReason: req.body.reason,
      location: req.body.location ?? item.location,
      meetingLink: req.body.meetingLink ?? item.meetingLink,
    },
  });
  await writeAudit(req, '面试改期', 'Interview', item.id, item, updated, req.body.reason);
  await writeActivity({
    type: 'INTERVIEW_RESCHEDULE',
    title: `面试已改期`,
    relatedId: item.id,
    actorId: req.user!.id,
    actorName: req.user!.name,
    detail: req.body.reason,
  });
  res.json(updated);
});

router.post('/:id/cancel', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.interview.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  if (!req.body.reason) return res.status(400).json({ message: '取消需填写原因' });
  const updated = await prisma.interview.update({
    where: { id: item.id },
    data: { status: 'CANCELLED', cancelReason: req.body.reason },
  });
  await completeTodos('Interview', item.id, 'EVALUATE');
  await writeAudit(req, '取消面试', 'Interview', item.id, item, updated, req.body.reason);
  res.json(updated);
});

router.post('/:id/attendance', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.interview.findUnique({
    where: { id: req.params.id },
    include: { interviewers: true, application: { include: { candidate: true } } },
  });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  const { status, note } = req.body;
  if (!['COMPLETED', 'NO_SHOW_CANDIDATE', 'NO_SHOW_INTERVIEWER'].includes(status)) {
    return res.status(400).json({ message: '无效到场状态' });
  }
  if (status !== 'COMPLETED' && !note) return res.status(400).json({ message: '异常到场需填写说明' });
  const updated = await prisma.interview.update({
    where: { id: item.id },
    data: { status, attendanceNote: note },
  });
  if (status === 'COMPLETED') {
    for (const iv of item.interviewers) {
      await prisma.todo.updateMany({
        where: { refType: 'Interview', refId: item.id, userId: iv.userId, type: 'EVALUATE', done: false },
        data: {
          title: `请提交面试评价：${item.application.candidate.name}`,
          dueAt: new Date(),
        },
      });
    }
  }
  res.json(updated);
});

router.post('/:id/evaluate', authRequired, async (req, res) => {
  const item = await prisma.interview.findUnique({
    where: { id: req.params.id },
    include: { interviewers: true, application: { include: { candidate: true, job: true } } },
  });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  const isInterviewer = item.interviewers.some((i) => i.userId === req.user!.id);
  if (!isInterviewer && req.user!.role !== 'ADMIN') {
    return res.status(403).json({ message: '仅本场面试官可提交评价' });
  }
  const { scores, strengths, risks, overall, conclusion, nextRound, submit } = req.body;
  if (submit) {
    if (!strengths || strengths.length < 20) return res.status(400).json({ message: '优势至少20字' });
    if (!risks) return res.status(400).json({ message: '请填写风险与疑点（无风险可选「暂未发现」）' });
    if (!overall || overall.length < 30) return res.status(400).json({ message: '总体评价至少30字' });
    if (!conclusion || !nextRound) return res.status(400).json({ message: '请选择面试结论与是否建议下一轮' });
  }

  const existing = await prisma.interviewEvaluation.findUnique({
    where: {
      interviewId_interviewerId: { interviewId: item.id, interviewerId: req.user!.id },
    },
  });
  if (existing?.status === 'SUBMITTED' && !req.body.correct) {
    return res.status(400).json({ message: '评价已提交锁定，确需修改请走更正流程' });
  }

  let evaluation;
  if (existing) {
    evaluation = await prisma.interviewEvaluation.update({
      where: { id: existing.id },
      data: {
        scores: JSON.stringify(scores || {}),
        strengths: strengths || existing.strengths,
        risks: risks || existing.risks,
        overall: overall || existing.overall,
        conclusion: conclusion || existing.conclusion,
        nextRound: nextRound || existing.nextRound,
        status: submit ? 'SUBMITTED' : req.body.correct ? 'CORRECTED' : 'DRAFT',
        submittedAt: submit ? new Date() : existing.submittedAt,
        previousContent: req.body.correct ? JSON.stringify(existing) : existing.previousContent,
        correctReason: req.body.correctReason,
      },
    });
  } else {
    evaluation = await prisma.interviewEvaluation.create({
      data: {
        interviewId: item.id,
        interviewerId: req.user!.id,
        scores: JSON.stringify(scores || {}),
        strengths: strengths || '',
        risks: risks || '',
        overall: overall || '',
        conclusion: conclusion || 'PENDING',
        nextRound: nextRound || 'YES',
        status: submit ? 'SUBMITTED' : 'DRAFT',
        submittedAt: submit ? new Date() : null,
      },
    });
  }

  if (submit) {
    await prisma.todo.updateMany({
      where: { refType: 'Interview', refId: item.id, userId: req.user!.id, type: 'EVALUATE', done: false },
      data: { done: true, doneAt: new Date() },
    });
    await writeActivity({
      type: 'EVALUATION_SUBMITTED',
      title: `${req.user!.name} 提交了面试评价`,
      jobId: item.application.jobId,
      relatedId: evaluation.id,
      actorId: req.user!.id,
      actorName: req.user!.name,
    });
  }
  res.json(evaluation);
});

router.post('/:id/round-result', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.interview.findUnique({
    where: { id: req.params.id },
    include: { application: { include: { candidate: true, job: true } }, evaluations: true },
  });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  const { result } = req.body;
  if (!['PASS', 'ADDITIONAL', 'PENDING', 'REJECT'].includes(result)) {
    return res.status(400).json({ message: '无效轮次结论' });
  }
  const updated = await prisma.interview.update({
    where: { id: item.id },
    data: {
      roundResult: result,
      roundResultBy: req.user!.id,
      roundResultAt: new Date(),
      status: item.status === 'SCHEDULED' ? 'COMPLETED' : item.status,
    },
  });

  if (result === 'REJECT') {
    await prisma.application.update({
      where: { id: item.applicationId },
      data: {
        status: 'REJECTED',
        rejectReason: req.body.reason || '面试未通过',
        rejectToPool: !!req.body.toPool,
      },
    });
    if (req.body.toPool) {
      await prisma.candidate.update({
        where: { id: item.application.candidateId },
        data: { inTalentPool: true, poolRemark: req.body.reason },
      });
    }
    await addProcessEvent({
      applicationId: item.applicationId,
      type: 'REJECT',
      fromStatus: item.application.status,
      toStatus: 'REJECTED',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      reason: req.body.reason,
    });
  } else if (result === 'PASS' && (item.round === 'FINAL' || req.body.toOffer)) {
    await prisma.application.update({
      where: { id: item.applicationId },
      data: { status: 'OFFER', stage: 'OFFER' },
    });
    if (item.application.job.hrOwnerId) {
      await createTodo({
        userId: item.application.job.hrOwnerId,
        type: 'APPROVE_OFFER',
        title: `可创建Offer：${item.application.candidate.name}`,
        refType: 'Application',
        refId: item.applicationId,
      });
    }
    await addProcessEvent({
      applicationId: item.applicationId,
      type: 'ADVANCE',
      fromStatus: item.application.status,
      toStatus: 'OFFER',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
    });
  }
  res.json(updated);
});

router.get('/:id/summary', authRequired, async (req, res) => {
  const item = await prisma.interview.findUnique({
    where: { id: req.params.id },
    include: {
      evaluations: { include: { interviewer: { select: { id: true, name: true } } } },
      application: { include: { candidate: true, job: true } },
    },
  });
  if (!item) return res.status(404).json({ message: '面试不存在' });
  const submitted = item.evaluations.filter((e) => e.status === 'SUBMITTED' || e.status === 'CORRECTED');
  const dims = ['professional', 'experience', 'problemSolving', 'communication', 'motivation', 'values'];
  const averages: Record<string, number | null> = {};
  for (const d of dims) {
    const vals = submitted
      .map((e) => {
        try {
          const s = JSON.parse(e.scores);
          return typeof s[d] === 'number' ? s[d] : null;
        } catch {
          return null;
        }
      })
      .filter((v): v is number => v != null);
    averages[d] = vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  }
  res.json({ interview: item, submitted, averages });
});

export default router;
