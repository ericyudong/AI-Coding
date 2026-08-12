import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, emitBusinessEvent } from '../utils/helpers';

const router = Router();

router.get('/', authRequired, async (req, res) => {
  const where: any = {};
  if (req.query.status) where.status = String(req.query.status);
  if (req.query.channel) where.channel = String(req.query.channel);
  const list = await prisma.messageLog.findMany({ where, orderBy: { createdAt: 'desc' }, take: 200 });
  res.json(list);
});

router.post('/send', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN', 'HR_OPS'), async (req, res) => {
  const { channel = 'EMAIL', toAddr, subject, content, templateKey, refType, refId } = req.body;
  if (!toAddr || !content) return res.status(400).json({ message: '收件人与内容必填' });

  // Simulate send with occasional failure + retry support
  const fail = Math.random() < 0.08;
  const log = await prisma.messageLog.create({
    data: {
      channel,
      templateKey,
      toAddr,
      subject,
      content,
      status: fail ? 'FAILED' : 'SENT',
      errorMsg: fail ? '模拟发送失败' : null,
      refType,
      refId,
      sentAt: fail ? null : new Date(),
    },
  });
  await writeAudit(req, '发送消息', 'MessageLog', log.id, null, { channel, toAddr, status: log.status });
  await emitBusinessEvent('MESSAGE_SENT', 'MessageLog', log.id, { status: log.status });
  if (fail) return res.status(502).json({ message: '发送失败，可重试', log });
  res.json(log);
});

router.post('/:id/retry', authRequired, requireRoles('HR', 'ADMIN'), async (req, res) => {
  const item = await prisma.messageLog.findUnique({ where: { id: String(req.params.id) } });
  if (!item) return res.status(404).json({ message: '记录不存在' });
  if (item.status !== 'FAILED') return res.status(400).json({ message: '仅失败消息可重试' });
  const fail = Math.random() < 0.1;
  const updated = await prisma.messageLog.update({
    where: { id: item.id },
    data: {
      status: fail ? 'FAILED' : 'SENT',
      retryCount: item.retryCount + 1,
      errorMsg: fail ? '重试仍失败（模拟）' : null,
      sentAt: fail ? null : new Date(),
    },
  });
  res.json(updated);
});

export default router;
