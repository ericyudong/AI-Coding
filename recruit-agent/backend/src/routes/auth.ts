import { Router } from 'express';
import bcrypt from 'bcryptjs';
import { prisma } from '../prisma';
import { authRequired, signToken, ROLE_LABELS } from '../middleware/auth';

const router = Router();

router.post('/login', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ message: '请输入用户名和密码' });
  }
  const user = await prisma.user.findUnique({
    where: { username },
    include: { org: true },
  });
  if (!user || !user.active) {
    return res.status(401).json({ message: '用户名或密码错误' });
  }
  const ok = await bcrypt.compare(password, user.passwordHash);
  if (!ok) return res.status(401).json({ message: '用户名或密码错误' });

  const authUser = {
    id: user.id,
    username: user.username,
    name: user.name,
    role: user.role,
    orgId: user.orgId,
    dataScope: user.dataScope,
  };
  const token = signToken(authUser);
  res.json({
    token,
    user: {
      ...authUser,
      email: user.email,
      phone: user.phone,
      orgName: user.org?.name,
      roleLabel: ROLE_LABELS[user.role] || user.role,
    },
  });
});

router.get('/me', authRequired, async (req, res) => {
  const user = await prisma.user.findUnique({
    where: { id: req.user!.id },
    include: { org: true },
  });
  if (!user) return res.status(404).json({ message: '用户不存在' });
  res.json({
    id: user.id,
    username: user.username,
    name: user.name,
    role: user.role,
    roleLabel: ROLE_LABELS[user.role] || user.role,
    orgId: user.orgId,
    orgName: user.org?.name,
    email: user.email,
    phone: user.phone,
    dataScope: user.dataScope,
  });
});

export default router;
