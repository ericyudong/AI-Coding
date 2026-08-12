import { Router } from 'express';
import crypto from 'crypto';
import { prisma } from '../prisma';
import { authRequired, requireRoles } from '../middleware/auth';
import { writeAudit, emitBusinessEvent, createTodo, addProcessEvent } from '../utils/helpers';

const router = Router();

function createToken() {
  return crypto.randomBytes(24).toString('hex');
}

router.post('/create', authRequired, requireRoles('HR', 'RECRUIT_LEAD', 'ADMIN'), async (req, res) => {
  const { type, candidateId, applicationId, interviewId, offerId, hours = 72, payload } = req.body;
  if (!type) return res.status(400).json({ message: '链接类型必填' });
  const expiresAt = new Date(Date.now() + Number(hours) * 3600000);
  const link = await prisma.secureLink.create({
    data: {
      token: createToken(),
      type,
      candidateId,
      applicationId,
      interviewId,
      offerId,
      expiresAt,
      payload: payload ? JSON.stringify(payload) : null,
    },
  });
  const url = `/portal/${link.token}`;
  await writeAudit(req, '创建候选人安全链接', 'SecureLink', link.id, null, { type, expiresAt });
  res.json({ ...link, url });
});

router.get('/portal/:token', async (req, res) => {
  const link = await prisma.secureLink.findUnique({
    where: { token: String(req.params.token) },
    include: {
      candidate: true,
      application: { include: { job: { include: { org: true } } } },
      interview: true,
      offer: true,
    },
  });
  if (!link || !link.active) return res.status(404).json({ message: '链接无效' });
  if (link.expiresAt < new Date()) return res.status(410).json({ message: '链接已过期' });

  const safeOffer = link.offer
    ? {
        id: link.offer.id,
        workLocation: link.offer.workLocation,
        level: link.offer.level,
        expectedHireDate: link.offer.expectedHireDate,
        validUntil: link.offer.validUntil,
        otherTerms: link.offer.otherTerms,
        baseSalary: link.offer.baseSalary,
        performance: link.offer.performance,
        bonus: link.offer.bonus,
        probationMonths: link.offer.probationMonths,
        status: link.offer.status,
      }
    : null;

  res.json({
    type: link.type,
    expiresAt: link.expiresAt,
    candidateName: link.candidate?.name,
    jobTitle: link.application?.job?.title,
    department: link.application?.job?.org?.name,
    interview: link.interview
      ? {
          id: link.interview.id,
          roundName: link.interview.roundName,
          startTime: link.interview.startTime,
          endTime: link.interview.endTime,
          method: link.interview.method,
          location: link.interview.location,
          meetingLink: link.interview.meetingLink,
          slotOptions: link.interview.slotOptions ? JSON.parse(link.interview.slotOptions) : [],
          selectedSlot: link.interview.selectedSlot,
          status: link.interview.status,
        }
      : null,
    offer: safeOffer,
    payload: link.payload ? JSON.parse(link.payload) : null,
  });
});

router.post('/portal/:token/confirm-interview', async (req, res) => {
  const link = await prisma.secureLink.findUnique({
    where: { token: String(req.params.token) },
    include: { interview: true },
  });
  if (!link || !link.active) return res.status(404).json({ message: '链接无效' });
  if (link.expiresAt < new Date()) return res.status(410).json({ message: '链接已过期' });
  if (link.type !== 'INTERVIEW_CONFIRM' && link.type !== 'SLOT_PICK') {
    return res.status(400).json({ message: '链接类型不匹配' });
  }
  if (!link.interviewId) return res.status(400).json({ message: '未关联面试' });

  const data: any = {};
  if (req.body.selectedSlot) data.selectedSlot = req.body.selectedSlot;
  if (req.body.startTime && req.body.endTime) {
    data.startTime = new Date(req.body.startTime);
    data.endTime = new Date(req.body.endTime);
  }
  await prisma.interview.update({ where: { id: link.interviewId }, data });
  await prisma.secureLink.update({ where: { id: link.id }, data: { usedAt: new Date() } });
  await emitBusinessEvent('INTERVIEW_CONFIRMED_BY_CANDIDATE', 'Interview', link.interviewId, {
    token: link.token,
  });
  res.json({ ok: true, message: '面试已确认' });
});

router.post('/portal/:token/confirm-offer', async (req, res) => {
  const link = await prisma.secureLink.findUnique({
    where: { token: String(req.params.token) },
    include: { offer: { include: { application: { include: { candidate: true, job: true } } } } },
  });
  if (!link || !link.active) return res.status(404).json({ message: '链接无效' });
  if (link.expiresAt < new Date()) return res.status(410).json({ message: '链接已过期' });
  if (link.type !== 'OFFER_CONFIRM' || !link.offer) return res.status(400).json({ message: '链接类型不匹配' });
  if (!['SENT', 'APPROVED'].includes(link.offer.status)) {
    return res.status(400).json({ message: 'Offer当前状态不可确认' });
  }

  const { result, declineReason } = req.body;
  if (!['ACCEPTED', 'DECLINED'].includes(result)) return res.status(400).json({ message: '请选择接受或拒绝' });
  if (result === 'DECLINED' && !declineReason) return res.status(400).json({ message: '拒绝需填写原因' });

  const device = req.headers['user-agent']?.toString().slice(0, 200) || 'unknown';
  const offer = await prisma.offer.update({
    where: { id: link.offer.id },
    data: {
      status: result,
      declineReason,
      resultAt: new Date(),
      onlineConfirmAt: new Date(),
      confirmDevice: device,
      confirmIp: req.ip,
    },
  });

  if (result === 'ACCEPTED') {
    const onboarding = await prisma.onboarding.create({
      data: {
        applicationId: link.offer.applicationId,
        offerId: offer.id,
        expectedDate: offer.expectedHireDate,
        status: 'PENDING_CONFIRM',
        materials: JSON.stringify([
          { name: '身份证复印件', status: 'PENDING' },
          { name: '学历证明', status: 'PENDING' },
          { name: '离职证明', status: 'PENDING' },
          { name: '体检报告', status: 'PENDING' },
          { name: '银行卡信息', status: 'PENDING' },
        ]),
      },
    });
    await prisma.application.update({
      where: { id: link.offer.applicationId },
      data: { status: 'ONBOARDING', stage: 'ONBOARDING' },
    });
    // collab tasks
    for (const dept of [
      { dept: 'HR', title: '准备劳动合同与入职材料' },
      { dept: 'ADMIN', title: '工位与门禁准备' },
      { dept: 'IT', title: '账号与设备准备' },
      { dept: 'HIRING_DEPT', title: '部门入职欢迎与导师安排' },
    ]) {
      await prisma.onboardCollabTask.create({ data: { onboardingId: onboarding.id, ...dept } });
    }
    const ops = await prisma.user.findMany({ where: { role: { in: ['HR_OPS', 'ADMIN'] }, active: true } });
    for (const u of ops) {
      await createTodo({
        userId: u.id,
        type: 'ONBOARDING',
        title: `待入职跟进：${link.offer.application.candidate.name}`,
        refType: 'Onboarding',
        refId: onboarding.id,
        dueAt: offer.expectedHireDate,
      });
    }
    await addProcessEvent({
      applicationId: link.offer.applicationId,
      type: 'OFFER_ACCEPTED',
      fromStatus: 'OFFER',
      toStatus: 'ONBOARDING',
      operatorName: '候选人外链确认',
    });
  } else {
    await prisma.application.update({
      where: { id: link.offer.applicationId },
      data: { status: 'WITHDRAWN', rejectReason: declineReason },
    });
  }

  await prisma.secureLink.update({ where: { id: link.id }, data: { usedAt: new Date(), active: false } });
  await emitBusinessEvent('OFFER_CONFIRMED_BY_CANDIDATE', 'Offer', offer.id, { result });
  res.json({ ok: true, result });
});

router.post('/portal/:token/supplement', async (req, res) => {
  const link = await prisma.secureLink.findUnique({ where: { token: String(req.params.token) } });
  if (!link || !link.active) return res.status(404).json({ message: '链接无效' });
  if (link.expiresAt < new Date()) return res.status(410).json({ message: '链接已过期' });
  if (!link.candidateId) return res.status(400).json({ message: '未关联候选人' });
  const updated = await prisma.candidate.update({
    where: { id: link.candidateId },
    data: {
      education: req.body.education,
      school: req.body.school,
      city: req.body.city,
      expectSalary: req.body.expectSalary,
      currentCompany: req.body.currentCompany,
      currentTitle: req.body.currentTitle,
    },
  });
  await prisma.secureLink.update({ where: { id: link.id }, data: { usedAt: new Date() } });
  res.json({ ok: true, candidateId: updated.id });
});

router.post('/portal/:token/feedback', async (req, res) => {
  const link = await prisma.secureLink.findUnique({ where: { token: String(req.params.token) } });
  if (!link || !link.candidateId) return res.status(404).json({ message: '链接无效' });
  if (link.expiresAt < new Date()) return res.status(410).json({ message: '链接已过期' });
  const fb = await prisma.candidateFeedback.create({
    data: {
      candidateId: link.candidateId,
      jobId: link.applicationId ? (await prisma.application.findUnique({ where: { id: link.applicationId } }))?.jobId : undefined,
      stage: req.body.stage || link.type,
      score: req.body.score != null ? Number(req.body.score) : null,
      comment: req.body.comment,
    },
  });
  res.json(fb);
});

export default router;
