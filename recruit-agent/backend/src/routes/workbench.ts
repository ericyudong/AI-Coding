import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired } from '../middleware/auth';

const router = Router();

router.get('/summary', authRequired, async (req, res) => {
  const userId = req.user!.id;
  const todos = await prisma.todo.findMany({
    where: { userId, done: false },
    orderBy: [{ dueAt: 'asc' }, { createdAt: 'desc' }],
    take: 50,
  });

  const todoGroups: Record<string, { count: number; earliest?: Date | null; items: typeof todos }> = {};
  for (const t of todos) {
    if (!todoGroups[t.type]) todoGroups[t.type] = { count: 0, earliest: null, items: [] };
    todoGroups[t.type].count += 1;
    todoGroups[t.type].items.push(t);
    if (!todoGroups[t.type].earliest || (t.dueAt && (!todoGroups[t.type].earliest || t.dueAt < todoGroups[t.type].earliest!))) {
      todoGroups[t.type].earliest = t.dueAt;
    }
  }

  const [openJobs, recruitingHeadcount, inProcess, sentOffers, pendingOnboard, hired] = await Promise.all([
    prisma.job.count({ where: { status: 'OPEN' } }),
    prisma.job.aggregate({ where: { status: 'OPEN' }, _sum: { headcount: true } }),
    prisma.application.count({
      where: { status: { in: ['NEW', 'HR_SCREEN', 'DEPT_SCREEN', 'INTERVIEW', 'OFFER', 'ONBOARDING'] } },
    }),
    prisma.offer.count({ where: { status: { in: ['SENT', 'ACCEPTED'] }, isActive: true } }),
    prisma.onboarding.count({ where: { status: { in: ['PENDING_CONFIRM', 'CONFIRMED', 'DELAYED'] } } }),
    prisma.application.count({ where: { status: 'HIRED' } }),
  ]);

  const activities = await prisma.activity.findMany({
    orderBy: { createdAt: 'desc' },
    take: 20,
  });

  res.json({
    todos,
    todoGroups,
    stats: {
      openJobs,
      recruitingHeadcount: recruitingHeadcount._sum.headcount || 0,
      inProcess,
      sentOffers,
      pendingOnboard,
      hired,
    },
    activities,
  });
});

router.post('/todos/:id/done', authRequired, async (req, res) => {
  const todo = await prisma.todo.findFirst({ where: { id: req.params.id, userId: req.user!.id } });
  if (!todo) return res.status(404).json({ message: '待办不存在' });
  const updated = await prisma.todo.update({
    where: { id: todo.id },
    data: { done: true, doneAt: new Date() },
  });
  res.json(updated);
});

export default router;
