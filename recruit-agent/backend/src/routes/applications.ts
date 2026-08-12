import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity, createTodo, completeTodos, addProcessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { jobId, status, keyword } = req.query;
  const where: Record<string, unknown> = {};
  if (jobId) where.jobId = String(jobId);
  if (status) where.status = String(status);
  const list = await prisma.application.findMany({
    where,
    include: {
      candidate: true,
      job: { include: { org: true, hrOwner: { select: { id: true, name: true } } } },
    },
    orderBy: { updatedAt: 'desc' },
  });
  const filtered = keyword
    ? list.filter(
        (a) =>
          a.candidate.name.includes(String(keyword)) ||
          (a.candidate.phone || '').includes(String(keyword)) ||
          a.job.title.includes(String(keyword))
      )
    : list;
  res.json(filtered);
});

router.get('/:id', authRequired, async (req, res) => {
  const app = await prisma.application.findUnique({
    where: { id: req.params.id },
    include: {
      candidate: { include: { remarks: { include: { createdBy: { select: { name: true } } } } } },
      job: { include: { org: true, hrOwner: true } },
      events: { orderBy: { createdAt: 'asc' } },
      interviews: {
        include: {
          interviewers: { include: { user: { select: { id: true, name: true } } } },
          evaluations: { include: { interviewer: { select: { id: true, name: true } } } },
        },
        orderBy: { startTime: 'asc' },
      },
      offers: { orderBy: { version: 'desc' } },
      onboarding: true,
    },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  res.json(app);
});

router.post('/:id/screen', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const app = await prisma.application.findUnique({
    where: { id: req.params.id },
    include: { candidate: true, job: true },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (!['NEW', 'HR_SCREEN'].includes(app.status)) {
    return res.status(400).json({ message: '当前不在HR筛选阶段' });
  }
  const { result, reason } = req.body;
  if (!['PASS', 'PENDING', 'REJECT'].includes(result)) {
    return res.status(400).json({ message: '请选择通过/待定/不通过' });
  }
  if (result !== 'PASS' && !reason) return res.status(400).json({ message: '待定或不通过需填写原因' });

  if (result === 'REJECT') {
    const updated = await prisma.application.update({
      where: { id: app.id },
      data: {
        status: 'REJECTED',
        screenResult: result,
        screenReason: reason,
        rejectReason: reason,
        rejectToPool: !!req.body.toPool,
      },
    });
    if (req.body.toPool) {
      await prisma.candidate.update({
        where: { id: app.candidateId },
        data: { inTalentPool: true, poolRemark: reason },
      });
    }
    await addProcessEvent({
      applicationId: app.id,
      type: 'REJECT',
      fromStatus: app.status,
      toStatus: 'REJECTED',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      reason,
    });
    await completeTodos('Application', app.id, 'SCREEN');
    await writeAudit(req, 'HR筛选淘汰', 'Application', app.id, app, updated, reason);
    return res.json(updated);
  }

  if (result === 'PENDING') {
    const updated = await prisma.application.update({
      where: { id: app.id },
      data: { screenResult: result, screenReason: reason },
    });
    await addProcessEvent({
      applicationId: app.id,
      type: 'SCREEN_PENDING',
      fromStatus: app.status,
      toStatus: app.status,
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      reason,
    });
    return res.json(updated);
  }

  // PASS -> next stage dept screen or interview
  const flow = (app.job.flowConfig || '').split(',');
  const hasDept = flow.includes('DEPT_SCREEN');
  const nextStatus = hasDept ? 'DEPT_SCREEN' : 'INTERVIEW';
  const updated = await prisma.application.update({
    where: { id: app.id },
    data: {
      status: nextStatus,
      stage: nextStatus,
      screenResult: 'PASS',
      screenReason: reason,
    },
  });
  await addProcessEvent({
    applicationId: app.id,
    type: 'ADVANCE',
    fromStatus: app.status,
    toStatus: nextStatus,
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    reason,
  });
  await completeTodos('Application', app.id, 'SCREEN');
  if (hasDept && app.job.requestId) {
    const request = await prisma.recruitRequest.findUnique({ where: { id: app.job.requestId } });
    if (request?.deptHeadId) {
      await createTodo({
        userId: request.deptHeadId,
        type: 'SCREEN',
        title: `部门筛选：${app.candidate.name} - ${app.job.title}`,
        refType: 'Application',
        refId: app.id,
      });
    }
  } else if (app.job.hrOwnerId) {
    await createTodo({
      userId: app.job.hrOwnerId,
      type: 'ARRANGE_INTERVIEW',
      title: `安排面试：${app.candidate.name} - ${app.job.title}`,
      refType: 'Application',
      refId: app.id,
    });
  }
  await writeActivity({
    type: 'PROCESS_ADVANCE',
    title: `${app.candidate.name} 通过HR筛选`,
    jobId: app.jobId,
    relatedId: app.id,
    actorId: req.user!.id,
    actorName: req.user!.name,
  });
  res.json(updated);
});

router.post('/:id/transfer-dept', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const app = await prisma.application.findUnique({
    where: { id: req.params.id },
    include: { candidate: true, job: true },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (!req.body.assigneeId) return res.status(400).json({ message: '请指定部门负责人' });
  const updated = await prisma.application.update({
    where: { id: app.id },
    data: {
      status: 'DEPT_SCREEN',
      stage: 'DEPT_SCREEN',
      assignedToId: req.body.assigneeId,
      focusPoints: req.body.focusPoints,
    },
  });
  await createTodo({
    userId: req.body.assigneeId,
    type: 'SCREEN',
    title: `部门筛选：${app.candidate.name} - ${app.job.title}`,
    refType: 'Application',
    refId: app.id,
  });
  await addProcessEvent({
    applicationId: app.id,
    type: 'TRANSFER',
    fromStatus: app.status,
    toStatus: 'DEPT_SCREEN',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    detail: req.body.focusPoints,
  });
  res.json(updated);
});

router.post('/:id/dept-feedback', authRequired, requireRoles('DEPT_HEAD', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const app = await prisma.application.findUnique({
    where: { id: req.params.id },
    include: { candidate: true, job: true },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (app.status !== 'DEPT_SCREEN') return res.status(400).json({ message: '当前不在部门筛选阶段' });
  const { result, comment } = req.body;
  if (!['PASS', 'REJECT', 'RETURN'].includes(result)) {
    return res.status(400).json({ message: '请选择通过/不通过/退回HR' });
  }
  if (!comment) return res.status(400).json({ message: '请填写意见' });

  if (result === 'REJECT') {
    const updated = await prisma.application.update({
      where: { id: app.id },
      data: {
        status: 'REJECTED',
        deptResult: result,
        deptComment: comment,
        rejectReason: comment,
        rejectToPool: !!req.body.toPool,
      },
    });
    if (req.body.toPool) {
      await prisma.candidate.update({
        where: { id: app.candidateId },
        data: { inTalentPool: true, poolRemark: comment },
      });
    }
    await completeTodos('Application', app.id, 'SCREEN');
    await addProcessEvent({
      applicationId: app.id,
      type: 'REJECT',
      fromStatus: app.status,
      toStatus: 'REJECTED',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      reason: comment,
    });
    return res.json(updated);
  }

  if (result === 'RETURN') {
    const updated = await prisma.application.update({
      where: { id: app.id },
      data: { status: 'HR_SCREEN', stage: 'HR_SCREEN', deptResult: result, deptComment: comment },
    });
    await completeTodos('Application', app.id, 'SCREEN');
    if (app.job.hrOwnerId) {
      await createTodo({
        userId: app.job.hrOwnerId,
        type: 'SCREEN',
        title: `补充信息后筛选：${app.candidate.name} - ${app.job.title}`,
        refType: 'Application',
        refId: app.id,
      });
    }
    await addProcessEvent({
      applicationId: app.id,
      type: 'RETURN',
      fromStatus: app.status,
      toStatus: 'HR_SCREEN',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      reason: comment,
    });
    return res.json(updated);
  }

  const updated = await prisma.application.update({
    where: { id: app.id },
    data: { status: 'INTERVIEW', stage: 'INTERVIEW', deptResult: 'PASS', deptComment: comment },
  });
  await completeTodos('Application', app.id, 'SCREEN');
  if (app.job.hrOwnerId) {
    await createTodo({
      userId: app.job.hrOwnerId,
      type: 'ARRANGE_INTERVIEW',
      title: `安排面试：${app.candidate.name} - ${app.job.title}`,
      refType: 'Application',
      refId: app.id,
    });
  }
  await addProcessEvent({
    applicationId: app.id,
    type: 'ADVANCE',
    fromStatus: app.status,
    toStatus: 'INTERVIEW',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    reason: comment,
  });
  res.json(updated);
});

router.post('/:id/reject', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'DEPT_HEAD', 'ADMIN'), async (req, res) => {
  const app = await prisma.application.findUnique({
    where: { id: req.params.id },
    include: { candidate: true, job: true },
  });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (['HIRED', 'REJECTED', 'WITHDRAWN'].includes(app.status)) {
    return res.status(400).json({ message: '终态记录不可直接淘汰' });
  }
  if (!req.body.reason) return res.status(400).json({ message: '淘汰必须填写原因' });
  const updated = await prisma.application.update({
    where: { id: app.id },
    data: {
      status: 'REJECTED',
      rejectReason: req.body.reason,
      rejectToPool: !!req.body.toPool,
    },
  });
  if (req.body.toPool) {
    await prisma.candidate.update({
      where: { id: app.candidateId },
      data: {
        inTalentPool: true,
        poolCategory: req.body.poolCategory,
        poolRemark: req.body.reason,
      },
    });
  }
  await completeTodos('Application', app.id);
  await addProcessEvent({
    applicationId: app.id,
    type: 'REJECT',
    fromStatus: app.status,
    toStatus: 'REJECTED',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    reason: req.body.reason,
  });
  await writeAudit(req, '淘汰候选人', 'Application', app.id, app, updated, req.body.reason);
  res.json(updated);
});

router.post('/:id/reactivate', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const app = await prisma.application.findUnique({ where: { id: req.params.id } });
  if (!app) return res.status(404).json({ message: '应聘记录不存在' });
  if (!['REJECTED', 'WITHDRAWN', 'TALENT_POOL'].includes(app.status)) {
    return res.status(400).json({ message: '仅终态可重新激活' });
  }
  if (!req.body.reason) return res.status(400).json({ message: '重新激活必须填写原因' });
  const updated = await prisma.application.update({
    where: { id: app.id },
    data: { status: 'HR_SCREEN', stage: 'HR_SCREEN' },
  });
  await addProcessEvent({
    applicationId: app.id,
    type: 'REACTIVATE',
    fromStatus: app.status,
    toStatus: 'HR_SCREEN',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    reason: req.body.reason,
  });
  await writeAudit(req, '重新激活', 'Application', app.id, app, updated, req.body.reason);
  res.json(updated);
});

router.post('/batch', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { ids, action, reason, toPool, assigneeId } = req.body;
  if (!Array.isArray(ids) || !ids.length) return res.status(400).json({ message: '请选择应聘记录' });
  const results = [];
  for (const id of ids) {
    const app = await prisma.application.findUnique({
      where: { id },
      include: { candidate: true, job: true },
    });
    if (!app) continue;
    if (action === 'reject') {
      if (!reason) return res.status(400).json({ message: '批量淘汰需统一原因' });
      const updated = await prisma.application.update({
        where: { id },
        data: { status: 'REJECTED', rejectReason: reason, rejectToPool: !!toPool },
      });
      if (toPool) {
        await prisma.candidate.update({
          where: { id: app.candidateId },
          data: { inTalentPool: true, poolRemark: reason },
        });
      }
      await addProcessEvent({
        applicationId: id,
        type: 'REJECT',
        fromStatus: app.status,
        toStatus: 'REJECTED',
        operatorId: req.user!.id,
        operatorName: req.user!.name,
        reason,
      });
      results.push(updated);
    } else if (action === 'pass') {
      const updated = await prisma.application.update({
        where: { id },
        data: { status: 'INTERVIEW', stage: 'INTERVIEW', screenResult: 'PASS' },
      });
      await addProcessEvent({
        applicationId: id,
        type: 'ADVANCE',
        fromStatus: app.status,
        toStatus: 'INTERVIEW',
        operatorId: req.user!.id,
        operatorName: req.user!.name,
      });
      results.push(updated);
    } else if (action === 'transfer' && assigneeId) {
      const updated = await prisma.application.update({
        where: { id },
        data: { status: 'DEPT_SCREEN', assignedToId: assigneeId },
      });
      await createTodo({
        userId: assigneeId,
        type: 'SCREEN',
        title: `部门筛选：${app.candidate.name}`,
        refType: 'Application',
        refId: id,
      });
      results.push(updated);
    } else if (action === 'toPool') {
      await prisma.candidate.update({
        where: { id: app.candidateId },
        data: { inTalentPool: true, poolRemark: reason },
      });
      results.push({ id, toPool: true });
    }
  }
  await writeAudit(req, `批量操作:${action}`, 'Application', undefined, null, { ids, action, reason });
  res.json({ count: results.length, results });
});

export default router;
