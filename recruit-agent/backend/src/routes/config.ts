import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { prisma } from '../prisma';
import { authRequired, requireRoles, ROLE_LABELS } from '../middleware/auth';
import { writeAudit } from '../utils/helpers';

const router = Router();

router.get('/dicts', authRequired, async (req, res) => {
  const { type } = req.query;
  const where = type ? { type: String(type), active: true } : { active: true };
  const list = await prisma.dictionary.findMany({ where, orderBy: [{ type: 'asc' }, { sort: 'asc' }] });
  res.json(list);
});

router.post('/dicts', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const { type, code, label, sort } = req.body;
  if (!type || !code || !label) return res.status(400).json({ message: '类型、编码、名称必填' });
  const item = await prisma.dictionary.create({
    data: { type, code, label, sort: sort || 0 },
  });
  res.json(item);
});

router.put('/dicts/:id', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const item = await prisma.dictionary.update({
    where: { id: req.params.id },
    data: {
      label: req.body.label,
      sort: req.body.sort,
      active: req.body.active,
    },
  });
  res.json(item);
});

router.get('/templates', authRequired, async (req, res) => {
  const { type } = req.query;
  const list = await prisma.template.findMany({
    where: type ? { type: String(type) } : undefined,
    orderBy: { updatedAt: 'desc' },
  });
  res.json(list);
});

router.post('/templates', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const item = await prisma.template.create({
    data: {
      type: req.body.type,
      name: req.body.name,
      content: req.body.content,
    },
  });
  res.json(item);
});

router.put('/templates/:id', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const item = await prisma.template.update({
    where: { id: req.params.id },
    data: {
      name: req.body.name,
      content: req.body.content,
      active: req.body.active,
    },
  });
  res.json(item);
});

router.get('/users', authRequired, requireRoles('ADMIN', 'RECRUIT_LEAD'), async (_req, res) => {
  const users = await prisma.user.findMany({
    include: { org: true },
    orderBy: { createdAt: 'desc' },
  });
  res.json(
    users.map((u) => ({
      id: u.id,
      username: u.username,
      name: u.name,
      email: u.email,
      phone: u.phone,
      role: u.role,
      roleLabel: ROLE_LABELS[u.role] || u.role,
      orgId: u.orgId,
      orgName: u.org?.name,
      active: u.active,
      dataScope: u.dataScope,
    }))
  );
});

router.post('/users', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const { username, password, name, role, orgId, email, phone, dataScope } = req.body;
  if (!username || !password || !name || !role) {
    return res.status(400).json({ message: '用户名、密码、姓名、角色必填' });
  }
  const exists = await prisma.user.findUnique({ where: { username } });
  if (exists) return res.status(400).json({ message: '用户名已存在' });
  const user = await prisma.user.create({
    data: {
      username,
      passwordHash: await bcrypt.hash(password, 10),
      name,
      role,
      orgId,
      email,
      phone,
      dataScope: dataScope || 'SELF',
    },
  });
  await writeAudit(req, '创建用户', 'User', user.id, null, { username, name, role });
  res.json({ id: user.id, username: user.username, name: user.name, role: user.role });
});

router.put('/users/:id', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const data: Record<string, unknown> = {
    name: req.body.name,
    role: req.body.role,
    orgId: req.body.orgId,
    email: req.body.email,
    phone: req.body.phone,
    dataScope: req.body.dataScope,
    active: req.body.active,
  };
  if (req.body.password) {
    data.passwordHash = await bcrypt.hash(req.body.password, 10);
  }
  const user = await prisma.user.update({ where: { id: req.params.id }, data });
  await writeAudit(req, '更新用户', 'User', user.id, null, { name: user.name, role: user.role, active: user.active });
  res.json(user);
});

router.get('/orgs', authRequired, async (_req, res) => {
  const orgs = await prisma.organization.findMany({ orderBy: { name: 'asc' } });
  res.json(orgs);
});

router.post('/orgs', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const org = await prisma.organization.create({
    data: { name: req.body.name, parentId: req.body.parentId },
  });
  res.json(org);
});

router.get('/audit-logs', authRequired, requireRoles('ADMIN'), async (req, res) => {
  const { objectType, keyword } = req.query;
  const where: Record<string, unknown> = {};
  if (objectType) where.objectType = String(objectType);
  if (keyword) {
    where.OR = [
      { action: { contains: String(keyword) } },
      { userName: { contains: String(keyword) } },
      { objectId: { contains: String(keyword) } },
    ];
  }
  const list = await prisma.auditLog.findMany({
    where,
    orderBy: { createdAt: 'desc' },
    take: 200,
  });
  res.json(list);
});

router.get('/roles', authRequired, async (_req, res) => {
  res.json(Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label })));
});

export default router;
