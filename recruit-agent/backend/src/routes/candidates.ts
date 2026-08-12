import { Router } from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, writeActivity, createTodo, addProcessEvent } from '../utils/helpers';

const router = Router();
const uploadDir = path.join(__dirname, '../../uploads');
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir, { recursive: true });

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, uploadDir),
  filename: (_req, file, cb) => {
    const safe = Buffer.from(file.originalname, 'latin1').toString('utf8');
    cb(null, `${Date.now()}-${safe}`);
  },
});
const upload = multer({
  storage,
  limits: { fileSize: 20 * 1024 * 1024 },
  fileFilter: (_req, file, cb) => {
    const ok = /\.(pdf|doc|docx|png|jpg|jpeg)$/i.test(file.originalname);
    if (!ok) return cb(new Error('仅支持 PDF/DOC/DOCX/图片'));
    cb(null, true);
  },
});

router.get('/', authRequired, async (req, res) => {
  const { keyword, source, city, inTalentPool } = req.query;
  const where: Record<string, unknown> = { deleted: false };
  if (source) where.source = String(source);
  if (city) where.city = String(city);
  if (inTalentPool === 'true') where.inTalentPool = true;
  if (keyword) {
    where.OR = [
      { name: { contains: String(keyword) } },
      { phone: { contains: String(keyword) } },
      { email: { contains: String(keyword) } },
      { currentCompany: { contains: String(keyword) } },
    ];
  }
  const list = await prisma.candidate.findMany({
    where,
    include: {
      applications: {
        include: { job: { select: { id: true, title: true, status: true } } },
        orderBy: { updatedAt: 'desc' },
      },
      remarks: { include: { createdBy: { select: { name: true } } }, orderBy: { createdAt: 'desc' } },
    },
    orderBy: { updatedAt: 'desc' },
  });
  res.json(list);
});

router.get('/check-duplicate', authRequired, async (req, res) => {
  const { phone, email } = req.query;
  const or: object[] = [];
  if (phone) or.push({ phone: String(phone) });
  if (email) or.push({ email: String(email) });
  if (!or.length) return res.json({ duplicates: [] });
  const duplicates = await prisma.candidate.findMany({
    where: { deleted: false, OR: or },
    select: { id: true, name: true, phone: true, email: true, currentCompany: true },
  });
  res.json({ duplicates });
});

router.get('/:id', authRequired, async (req, res) => {
  const item = await prisma.candidate.findUnique({
    where: { id: req.params.id },
    include: {
      remarks: { include: { createdBy: { select: { id: true, name: true } } }, orderBy: { createdAt: 'desc' } },
      applications: {
        include: {
          job: true,
          interviews: { include: { evaluations: true, interviewers: { include: { user: true } } } },
          offers: { orderBy: { version: 'desc' } },
          onboarding: true,
          events: { orderBy: { createdAt: 'asc' } },
        },
        orderBy: { updatedAt: 'desc' },
      },
    },
  });
  if (!item || item.deleted) return res.status(404).json({ message: '候选人不存在' });
  res.json(item);
});

router.post('/', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const body = req.body;
  if (!body.name) return res.status(400).json({ message: '姓名必填' });
  if (!body.phone && !body.email) return res.status(400).json({ message: '手机号或邮箱至少填写一项' });
  if (!body.source) return res.status(400).json({ message: '简历来源必填' });

  if (!body.forceCreate) {
    const or: object[] = [];
    if (body.phone) or.push({ phone: body.phone });
    if (body.email) or.push({ email: body.email });
    if (or.length) {
      const duplicates = await prisma.candidate.findMany({
        where: { deleted: false, OR: or },
        select: { id: true, name: true, phone: true, email: true },
      });
      if (duplicates.length) {
        return res.status(409).json({ message: '发现疑似重复候选人', duplicates });
      }
    }
  }

  const candidate = await prisma.candidate.create({
    data: {
      name: body.name,
      phone: body.phone,
      email: body.email,
      gender: body.gender,
      education: body.education,
      school: body.school,
      currentCompany: body.currentCompany,
      currentTitle: body.currentTitle,
      yearsOfExp: body.yearsOfExp != null ? Number(body.yearsOfExp) : null,
      city: body.city,
      expectSalary: body.expectSalary,
      source: body.source,
      sourceRemark: body.sourceRemark,
      tags: Array.isArray(body.tags) ? body.tags.join(',') : body.tags,
    },
  });

  let application = null;
  if (body.jobId) {
    const job = await prisma.job.findUnique({ where: { id: body.jobId } });
    if (!job) return res.status(400).json({ message: '关联职位不存在' });
    if (job.status === 'CLOSED') return res.status(400).json({ message: '职位已关闭，不可新增应聘记录' });
    application = await prisma.application.create({
      data: {
        candidateId: candidate.id,
        jobId: body.jobId,
        status: 'HR_SCREEN',
        stage: 'HR_SCREEN',
      },
    });
    await addProcessEvent({
      applicationId: application.id,
      type: 'ENTER',
      toStatus: 'HR_SCREEN',
      toStage: 'HR_SCREEN',
      operatorId: req.user!.id,
      operatorName: req.user!.name,
      detail: '新增候选人并关联职位',
    });
    if (job.hrOwnerId) {
      await createTodo({
        userId: job.hrOwnerId,
        type: 'SCREEN',
        title: `筛选候选人：${candidate.name} - ${job.title}`,
        refType: 'Application',
        refId: application.id,
      });
    }
    await writeActivity({
      type: 'CANDIDATE_ENTER',
      title: `${candidate.name} 进入职位 ${job.title}`,
      jobId: job.id,
      relatedId: application.id,
      actorId: req.user!.id,
      actorName: req.user!.name,
    });
  }

  await writeAudit(req, '新增候选人', 'Candidate', candidate.id, null, candidate);
  res.json({ candidate, application });
});

router.put('/:id', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const item = await prisma.candidate.findUnique({ where: { id: req.params.id } });
  if (!item || item.deleted) return res.status(404).json({ message: '候选人不存在' });
  const body = req.body;
  const updated = await prisma.candidate.update({
    where: { id: item.id },
    data: {
      name: body.name ?? item.name,
      phone: body.phone ?? item.phone,
      email: body.email ?? item.email,
      gender: body.gender ?? item.gender,
      education: body.education ?? item.education,
      school: body.school ?? item.school,
      currentCompany: body.currentCompany ?? item.currentCompany,
      currentTitle: body.currentTitle ?? item.currentTitle,
      yearsOfExp: body.yearsOfExp != null ? Number(body.yearsOfExp) : item.yearsOfExp,
      city: body.city ?? item.city,
      expectSalary: body.expectSalary ?? item.expectSalary,
      source: body.source ?? item.source,
      sourceRemark: body.sourceRemark ?? item.sourceRemark,
      tags: body.tags != null ? (Array.isArray(body.tags) ? body.tags.join(',') : body.tags) : item.tags,
    },
  });
  await writeAudit(req, '更新候选人', 'Candidate', item.id, item, updated);
  res.json(updated);
});

router.post('/:id/resume', authRequired, upload.single('file'), async (req, res) => {
  const item = await prisma.candidate.findUnique({ where: { id: req.params.id } });
  if (!item) return res.status(404).json({ message: '候选人不存在' });
  if (!req.file) return res.status(400).json({ message: '请上传文件' });
  const updated = await prisma.candidate.update({
    where: { id: item.id },
    data: { resumePath: req.file.filename },
  });
  await writeAudit(req, '上传简历', 'Candidate', item.id, null, { file: req.file.filename });
  res.json(updated);
});

router.post('/:id/remark', authRequired, async (req, res) => {
  if (!req.body.content) return res.status(400).json({ message: '备注内容不能为空' });
  const remark = await prisma.candidateRemark.create({
    data: {
      candidateId: req.params.id,
      content: req.body.content,
      createdById: req.user!.id,
    },
    include: { createdBy: { select: { name: true } } },
  });
  res.json(remark);
});

router.post('/:id/link-job', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const candidate = await prisma.candidate.findUnique({ where: { id: req.params.id } });
  if (!candidate || candidate.deleted) return res.status(404).json({ message: '候选人不存在' });
  const job = await prisma.job.findUnique({ where: { id: req.body.jobId } });
  if (!job) return res.status(404).json({ message: '职位不存在' });
  if (job.status === 'CLOSED') return res.status(400).json({ message: '职位已关闭，不可新增应聘记录' });
  const exists = await prisma.application.findFirst({
    where: { candidateId: candidate.id, jobId: job.id, status: { notIn: ['REJECTED', 'WITHDRAWN', 'HIRED'] } },
  });
  if (exists) return res.status(400).json({ message: '该候选人已有进行中的同职位应聘记录' });

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
    type: 'ENTER',
    toStatus: 'HR_SCREEN',
    operatorId: req.user!.id,
    operatorName: req.user!.name,
    detail: '关联职位生成应聘记录',
  });
  if (job.hrOwnerId) {
    await createTodo({
      userId: job.hrOwnerId,
      type: 'SCREEN',
      title: `筛选候选人：${candidate.name} - ${job.title}`,
      refType: 'Application',
      refId: application.id,
    });
  }
  await writeAudit(req, '关联职位', 'Application', application.id, null, application);
  res.json(application);
});

router.post('/import', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const rows = req.body.rows as Array<Record<string, string>>;
  if (!Array.isArray(rows) || !rows.length) return res.status(400).json({ message: '请提供导入数据' });
  const results: { success: number; failed: { row: number; reason: string }[] } = { success: 0, failed: [] };
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    try {
      if (!row.name) throw new Error('姓名必填');
      if (!row.phone && !row.email) throw new Error('手机号或邮箱至少一项');
      if (!row.source) throw new Error('来源必填');
      await prisma.candidate.create({
        data: {
          name: row.name,
          phone: row.phone || null,
          email: row.email || null,
          education: row.education || null,
          currentCompany: row.currentCompany || null,
          currentTitle: row.currentTitle || null,
          city: row.city || null,
          source: row.source,
          sourceRemark: row.sourceRemark || null,
        },
      });
      results.success += 1;
    } catch (e) {
      results.failed.push({ row: i + 1, reason: e instanceof Error ? e.message : '导入失败' });
    }
  }
  await writeAudit(req, '批量导入候选人', 'Candidate', undefined, null, results);
  res.json(results);
});

export default router;
