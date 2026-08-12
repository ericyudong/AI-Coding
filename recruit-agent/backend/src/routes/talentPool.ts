import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, createTodo, addProcessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const { keyword, education, city, category, tag } = req.query;
  const where: Record<string, unknown> = { deleted: false, inTalentPool: true };
  if (education) where.education = String(education);
  if (city) where.city = String(city);
  if (category) where.poolCategory = String(category);
  if (keyword) {
    where.OR = [
      { name: { contains: String(keyword) } },
      { phone: { contains: String(keyword) } },
      { currentCompany: { contains: String(keyword) } },
      { poolRemark: { contains: String(keyword) } },
      { tags: { contains: String(keyword) } },
    ];
  }
  let list = await prisma.candidate.findMany({
    where,
    include: {
      applications: {
        include: {
          job: { select: { title: true } },
          interviews: { include: { evaluations: true } },
        },
        orderBy: { updatedAt: 'desc' },
        take: 5,
      },
    },
    orderBy: { updatedAt: 'desc' },
  });
  if (tag) {
    list = list.filter((c) => (c.tags || '').split(',').includes(String(tag)));
  }
  res.json(list);
});

router.post('/:candidateId/add', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const candidate = await prisma.candidate.findUnique({ where: { id: req.params.candidateId } });
  if (!candidate) return res.status(404).json({ message: '候选人不存在' });
  const updated = await prisma.candidate.update({
    where: { id: candidate.id },
    data: {
      inTalentPool: true,
      poolCategory: req.body.poolCategory,
      poolRemark: req.body.poolRemark,
      poolSuitable: req.body.poolSuitable,
      poolRisk: req.body.poolRisk,
      poolContactAt: req.body.poolContactAt,
      tags: req.body.tags != null ? (Array.isArray(req.body.tags) ? req.body.tags.join(',') : req.body.tags) : candidate.tags,
    },
  });
  await writeAudit(req, '加入人才库', 'Candidate', candidate.id, candidate, updated);
  res.json(updated);
});

router.post('/:candidateId/remove', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const updated = await prisma.candidate.update({
    where: { id: req.params.candidateId },
    data: { inTalentPool: false },
  });
  await writeAudit(req, '移出人才库', 'Candidate', updated.id, null, updated, req.body.reason);
  res.json(updated);
});

router.post('/:candidateId/reapply', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const candidate = await prisma.candidate.findUnique({ where: { id: req.params.candidateId } });
  if (!candidate || !candidate.inTalentPool) return res.status(404).json({ message: '人才库候选人不存在' });
  const job = await prisma.job.findUnique({ where: { id: req.body.jobId } });
  if (!job) return res.status(404).json({ message: '职位不存在' });
  if (job.status === 'CLOSED') return res.status(400).json({ message: '职位已关闭' });

  const application = await prisma.application.create({
    data: {
      candidateId: candidate.id,
      jobId: job.id,
      status: 'HR_SCREEN',
      stage: 'HR_SCREEN',
    },
  });
  await addProcessEvent({
    applicationId: application.id,
    type: 'REAPPLY',
    toStatus: 'HR_SCREEN',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    detail: '从人才库重新应聘',
  });
  if (job.hrOwnerId) {
    await createTodo({
      userId: job.hrOwnerId,
      type: 'SCREEN',
      title: `人才库重新应聘筛选：${candidate.name} - ${job.title}`,
      refType: 'Application',
      refId: application.id,
    });
  }
  await writeAudit(req, '人才库重新应聘', 'Application', application.id, null, application);
  res.json(application);
});

export default router;
