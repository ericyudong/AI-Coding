import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { status, keyword } = req.query;
  const where: Record<string, unknown> = {};
  if (status) where.status = String(status);
  if (keyword) {
    where.OR = [
      { title: { contains: String(keyword) } },
      { workLocation: { contains: String(keyword) } },
    ];
  }
  const list = await prisma.job.findMany({
    where,
    include: {
      org: true,
      request: true,
      hrOwner: { select: { id: true, name: true } },
      _count: { select: { applications: true } },
    },
    orderBy: { updatedAt: 'desc' },
  });
  res.json(list);
});

router.get('/:id', authRequired, async (req, res) => {
  const job = await prisma.job.findUnique({
    where: { id: req.params.id },
    include: {
      org: true,
      request: true,
      hrOwner: true,
      applications: {
        include: { candidate: true },
        orderBy: { updatedAt: 'desc' },
      },
    },
  });
  if (!job) return res.status(404).json({ message: '职位不存在' });

  const stageCounts: Record<string, number> = {};
  for (const app of job.applications) {
    stageCounts[app.status] = (stageCounts[app.status] || 0) + 1;
  }
  res.json({ ...job, stageCounts });
});

router.post('/', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { requestId, title, headcount, workLocation, salaryMin, salaryMax, responsibilities, requirements, bonuses, hrOwnerId, flowConfig } = req.body;
  if (!requestId) return res.status(400).json({ message: '请选择招聘需求' });
  const request = await prisma.recruitRequest.findUnique({ where: { id: requestId } });
  if (!request) return res.status(404).json({ message: '需求不存在' });
  if (!['APPROVED', 'RECRUITING'].includes(request.status)) {
    return res.status(400).json({ message: '仅审批通过且未关闭的需求可创建职位' });
  }
  const job = await prisma.job.create({
    data: {
      requestId,
      orgId: request.orgId,
      title: title || request.positionTitle,
      headcount: headcount != null ? Number(headcount) : request.headcount,
      workLocation: workLocation || request.workLocation,
      salaryMin: salaryMin != null ? Number(salaryMin) : request.salaryMin,
      salaryMax: salaryMax != null ? Number(salaryMax) : request.salaryMax,
      responsibilities,
      requirements,
      bonuses,
      hrOwnerId: hrOwnerId || request.hrOwnerId,
      flowConfig: flowConfig || 'HR_SCREEN,DEPT_SCREEN,FIRST_INTERVIEW,SECOND_INTERVIEW,OFFER',
      status: 'DRAFT',
    },
  });
  if (request.status === 'APPROVED') {
    await prisma.recruitRequest.update({ where: { id: request.id }, data: { status: 'RECRUITING' } });
  }
  await writeAudit(req, '创建职位', 'Job', job.id, null, job);
  res.json(job);
});

router.put('/:id', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const job = await prisma.job.findUnique({ where: { id: req.params.id } });
  if (!job) return res.status(404).json({ message: '职位不存在' });
  const body = req.body;
  const updated = await prisma.job.update({
    where: { id: job.id },
    data: {
      title: body.title ?? job.title,
      headcount: body.headcount != null ? Number(body.headcount) : job.headcount,
      workLocation: body.workLocation ?? job.workLocation,
      salaryMin: body.salaryMin != null ? Number(body.salaryMin) : job.salaryMin,
      salaryMax: body.salaryMax != null ? Number(body.salaryMax) : job.salaryMax,
      responsibilities: body.responsibilities ?? job.responsibilities,
      requirements: body.requirements ?? job.requirements,
      bonuses: body.bonuses ?? job.bonuses,
      hrOwnerId: body.hrOwnerId ?? job.hrOwnerId,
      flowConfig: body.flowConfig ?? job.flowConfig,
      evalTemplateId: body.evalTemplateId ?? job.evalTemplateId,
    },
  });
  await writeAudit(req, '修改职位JD', 'Job', job.id, job, updated);
  res.json(updated);
});

router.post('/:id/publish', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const job = await prisma.job.findUnique({ where: { id: req.params.id }, include: { org: true } });
  if (!job) return res.status(404).json({ message: '职位不存在' });
  const salary =
    job.salaryMin != null || job.salaryMax != null
      ? `${job.salaryMin ?? ''}-${job.salaryMax ?? ''}K`
      : '面议';
  const publishCopy =
    req.body.publishCopy ||
    `【招聘】${job.title}\n部门：${job.org.name}\n地点：${job.workLocation}\n人数：${job.headcount}\n薪资：${salary}\n\n工作职责：\n${job.responsibilities || '详见职位描述'}\n\n任职要求：\n${job.requirements || '详见职位描述'}`;
  const updated = await prisma.job.update({
    where: { id: job.id },
    data: { status: 'OPEN', publishCopy },
  });
  await writeAudit(req, '发布职位', 'Job', job.id, job, updated);
  await writeActivity({
    type: 'JOB_PUBLISHED',
    title: `职位已发布：${job.title}`,
    jobId: job.id,
    actorId: req.user!.id,
    actorName: req.user!.name,
  });
  res.json(updated);
});

router.post('/:id/status', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const job = await prisma.job.findUnique({ where: { id: req.params.id } });
  if (!job) return res.status(404).json({ message: '职位不存在' });
  const { status, reason } = req.body;
  if (!['OPEN', 'PAUSED', 'CLOSED'].includes(status)) {
    return res.status(400).json({ message: '无效状态' });
  }
  if (status === 'CLOSED' && !reason) {
    return res.status(400).json({ message: '关闭职位必须填写原因' });
  }
  const updated = await prisma.job.update({ where: { id: job.id }, data: { status } });
  await writeAudit(req, `职位状态变更为${status}`, 'Job', job.id, job, updated, reason);
  res.json(updated);
});

export default router;
