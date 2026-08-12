import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit } from '../utils/helpers';

const router = Router();

router.get('/eval-models', authRequired, async (_req, res) => {
  const list = await prisma.evalModel.findMany({ where: { active: true }, orderBy: { updatedAt: 'desc' } });
  res.json(list);
});

router.post('/eval-models', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (req, res) => {
  const body = req.body;
  if (!body.name || !body.dimensions) return res.status(400).json({ message: '名称与维度必填' });
  const item = await prisma.evalModel.create({
    data: {
      name: body.name,
      jobFamily: body.jobFamily,
      dimensions: typeof body.dimensions === 'string' ? body.dimensions : JSON.stringify(body.dimensions),
      passScore: body.passScore != null ? Number(body.passScore) : 3,
      version: body.version || 1,
      isLatest: true,
    },
  });
  res.json(item);
});

router.get('/calibration', authRequired, async (_req, res) => {
  const evals = await prisma.interviewEvaluation.findMany({
    where: { status: { in: ['SUBMITTED', 'CORRECTED'] } },
    include: { interviewer: { select: { id: true, name: true } } },
  });
  const byInterviewer: Record<string, { name: string; count: number; avg: number | null; scores: number[] }> = {};
  for (const e of evals) {
    const key = e.interviewerId;
    if (!byInterviewer[key]) byInterviewer[key] = { name: e.interviewer.name, count: 0, avg: null, scores: [] };
    byInterviewer[key].count += 1;
    try {
      const s = JSON.parse(e.scores);
      const vals = Object.values(s).filter((v): v is number => typeof v === 'number');
      if (vals.length) byInterviewer[key].scores.push(vals.reduce((a, b) => a + b, 0) / vals.length);
    } catch {
      /* ignore */
    }
  }
  const rows = Object.values(byInterviewer).map((r) => ({
    name: r.name,
    count: r.count,
    avg: r.scores.length ? Math.round((r.scores.reduce((a, b) => a + b, 0) / r.scores.length) * 100) / 100 : null,
  }));
  res.json({ interviewers: rows, totalEvaluations: evals.length });
});

router.get('/', authRequired, async (req, res) => {
  const { family, latest } = req.query;
  const where: any = { active: true };
  if (family) where.family = String(family);
  if (latest !== 'false') where.isLatest = true;
  const list = await prisma.jobStandard.findMany({ where, orderBy: [{ code: 'asc' }, { version: 'desc' }] });
  res.json(list);
});

router.get('/:id', authRequired, async (req, res) => {
  const item = await prisma.jobStandard.findUnique({ where: { id: String(req.params.id) } });
  if (!item) return res.status(404).json({ message: '岗位标准不存在' });
  res.json(item);
});

router.post('/', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD', 'HR'), async (req, res) => {
  const body = req.body;
  if (!body.code || !body.name) return res.status(400).json({ message: '编码和名称必填' });
  const max = await prisma.jobStandard.aggregate({ where: { code: body.code }, _max: { version: true } });
  const version = (max._max.version || 0) + 1;
  if (version > 1) {
    await prisma.jobStandard.updateMany({ where: { code: body.code, isLatest: true }, data: { isLatest: false } });
  }
  const item = await prisma.jobStandard.create({
    data: {
      code: body.code,
      name: body.name,
      family: body.family,
      version,
      isLatest: true,
      parentCode: body.parentCode,
      jd: body.jd,
      requirements: body.requirements,
      hardCriteria: typeof body.hardCriteria === 'string' ? body.hardCriteria : JSON.stringify(body.hardCriteria || []),
      experienceReq: body.experienceReq,
      skills: typeof body.skills === 'string' ? body.skills : JSON.stringify(body.skills || []),
      softSkills: typeof body.softSkills === 'string' ? body.softSkills : JSON.stringify(body.softSkills || []),
      motivationItems: typeof body.motivationItems === 'string' ? body.motivationItems : JSON.stringify(body.motivationItems || []),
      riskItems: typeof body.riskItems === 'string' ? body.riskItems : JSON.stringify(body.riskItems || []),
      flowTemplateId: body.flowTemplateId,
      evalModelId: body.evalModelId,
      defaultOwnerId: body.defaultOwnerId,
      interviewRounds: typeof body.interviewRounds === 'string' ? body.interviewRounds : JSON.stringify(body.interviewRounds || []),
    },
  });
  await writeAudit(req, version > 1 ? '岗位标准新版本' : '创建岗位标准', 'JobStandard', item.id, null, item);
  res.json(item);
});

router.post('/apply-to-job/:jobId', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const standard = await prisma.jobStandard.findUnique({ where: { id: req.body.standardId } });
  if (!standard) return res.status(404).json({ message: '标准不存在' });
  const job = await prisma.job.update({
    where: { id: String(req.params.jobId) },
    data: {
      standardId: standard.id,
      standardVersion: standard.version,
      flowTemplateId: standard.flowTemplateId || undefined,
      evalModelId: standard.evalModelId || undefined,
      responsibilities: standard.jd || undefined,
      requirements: standard.requirements || undefined,
    },
  });
  await writeAudit(req, '应用岗位标准到职位', 'Job', job.id, null, { standardId: standard.id, version: standard.version });
  res.json(job);
});

export default router;
