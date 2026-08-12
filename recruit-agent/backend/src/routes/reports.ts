import { Router } from 'express';
import { prisma } from '../prisma';
import { authRequired } from '../middleware/auth';
import { writeAudit } from '../utils/helpers';

const router = Router();

router.get('/overview', authRequired, async (_req, res) => {
  const requests = await prisma.recruitRequest.findMany({
    include: { org: true, hrOwner: { select: { name: true } }, jobs: true },
  });
  const requestStats = requests.map((r) => {
    const inProcess = r.headcount - r.hiredCount;
    return {
      id: r.id,
      name: r.name,
      orgName: r.org.name,
      positionTitle: r.positionTitle,
      headcount: r.headcount,
      hiredCount: r.hiredCount,
      pendingOnboard: 0,
      inProcess: Math.max(inProcess, 0),
      gap: Math.max(r.headcount - r.hiredCount, 0),
      status: r.status,
      hrOwner: r.hrOwner?.name,
    };
  });

  // enrich pending onboard
  const onboardings = await prisma.onboarding.findMany({
    where: { status: { in: ['PENDING_CONFIRM', 'CONFIRMED', 'DELAYED'] } },
    include: { application: { include: { job: true } } },
  });
  for (const o of onboardings) {
    const row = requestStats.find((r) => r.id === o.application.job.requestId);
    if (row) row.pendingOnboard += 1;
  }

  res.json({ requests: requestStats });
});

router.get('/funnel', authRequired, async (req, res) => {
  const { jobId, from, to } = req.query;
  const where: Record<string, unknown> = {};
  if (jobId) where.jobId = String(jobId);
  if (from || to) {
    where.enteredAt = {};
    if (from) (where.enteredAt as Record<string, Date>).gte = new Date(String(from));
    if (to) (where.enteredAt as Record<string, Date>).lte = new Date(String(to));
  }
  const apps = await prisma.application.findMany({ where, include: { interviews: true, offers: true } });
  const entered = apps.length;
  const screenPass = apps.filter((a) =>
    ['DEPT_SCREEN', 'INTERVIEW', 'OFFER', 'ONBOARDING', 'HIRED'].includes(a.status) || a.screenResult === 'PASS'
  ).length;
  const interviewed = apps.filter((a) => a.interviews.length > 0).length;
  const interviewPass = apps.filter((a) => ['OFFER', 'ONBOARDING', 'HIRED'].includes(a.status)).length;
  const offerSent = apps.filter((a) => a.offers.some((o) => ['SENT', 'ACCEPTED', 'DECLINED', 'EXPIRED'].includes(o.status))).length;
  const offerAccepted = apps.filter((a) => a.offers.some((o) => o.status === 'ACCEPTED') || ['ONBOARDING', 'HIRED'].includes(a.status)).length;
  const hired = apps.filter((a) => a.status === 'HIRED').length;

  const rate = (n: number, d: number) => (d === 0 ? 0 : Math.round((n / d) * 1000) / 10);
  res.json({
    stages: [
      { key: 'entered', label: '新增简历', count: entered, rate: 100 },
      { key: 'screenPass', label: '筛选通过', count: screenPass, rate: rate(screenPass, entered) },
      { key: 'interviewed', label: '进入面试', count: interviewed, rate: rate(interviewed, entered) },
      { key: 'interviewPass', label: '面试通过', count: interviewPass, rate: rate(interviewPass, entered) },
      { key: 'offerSent', label: 'Offer发送', count: offerSent, rate: rate(offerSent, entered) },
      { key: 'offerAccepted', label: 'Offer接受', count: offerAccepted, rate: rate(offerAccepted, entered) },
      { key: 'hired', label: '入职', count: hired, rate: rate(hired, entered) },
    ],
  });
});

router.get('/cycle', authRequired, async (_req, res) => {
  const events = await prisma.processEvent.findMany({ orderBy: { createdAt: 'asc' } });
  const apps = await prisma.application.findMany({
    include: { events: true, offers: true, onboarding: true, job: { include: { request: true } } },
  });
  const cycles: { applicationId: string; totalDays: number | null; stages: Record<string, number | null> }[] = [];
  for (const app of apps) {
    const enter = app.events.find((e) => e.type === 'ENTER')?.createdAt || app.enteredAt;
    const firstInterview = app.events.find((e) => e.type === 'INTERVIEW_SCHEDULED')?.createdAt;
    const offerEvent = app.events.find((e) => e.toStatus === 'OFFER')?.createdAt;
    const hiredEvent = app.events.find((e) => e.type === 'HIRED')?.createdAt;
    const days = (a?: Date | null, b?: Date | null) =>
      a && b ? Math.round((b.getTime() - a.getTime()) / 86400000) : null;
    cycles.push({
      applicationId: app.id,
      totalDays: days(enter, hiredEvent),
      stages: {
        enterToInterview: days(enter, firstInterview),
        interviewToOffer: days(firstInterview, offerEvent),
        offerToHire: days(offerEvent, hiredEvent),
      },
    });
  }
  const avg = (vals: (number | null)[]) => {
    const nums = vals.filter((v): v is number => v != null);
    return nums.length ? Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10 : null;
  };
  res.json({
    average: {
      totalDays: avg(cycles.map((c) => c.totalDays)),
      enterToInterview: avg(cycles.map((c) => c.stages.enterToInterview)),
      interviewToOffer: avg(cycles.map((c) => c.stages.interviewToOffer)),
      offerToHire: avg(cycles.map((c) => c.stages.offerToHire)),
    },
    samples: cycles.slice(0, 50),
    eventCount: events.length,
  });
});

router.get('/channels', authRequired, async (_req, res) => {
  const candidates = await prisma.candidate.findMany({
    where: { deleted: false },
    include: {
      applications: { include: { interviews: true, offers: true } },
    },
  });
  const map: Record<string, { source: string; resumes: number; interviews: number; offers: number; hired: number }> = {};
  for (const c of candidates) {
    if (!map[c.source]) map[c.source] = { source: c.source, resumes: 0, interviews: 0, offers: 0, hired: 0 };
    map[c.source].resumes += 1;
    for (const a of c.applications) {
      if (a.interviews.length) map[c.source].interviews += 1;
      if (a.offers.some((o) => ['SENT', 'ACCEPTED', 'DECLINED'].includes(o.status))) map[c.source].offers += 1;
      if (a.status === 'HIRED') map[c.source].hired += 1;
    }
  }
  res.json(Object.values(map));
});

router.get('/reasons', authRequired, async (_req, res) => {
  const apps = await prisma.application.findMany({
    where: { status: { in: ['REJECTED', 'WITHDRAWN'] } },
  });
  const offers = await prisma.offer.findMany({ where: { status: 'DECLINED' } });
  const onboardings = await prisma.onboarding.findMany({ where: { status: 'ABANDONED' } });

  const countBy = (items: { reason?: string | null }[], field: 'reason') => {
    const m: Record<string, number> = {};
    for (const i of items) {
      const k = i[field] || '未填写';
      m[k] = (m[k] || 0) + 1;
    }
    return Object.entries(m).map(([reason, count]) => ({ reason, count }));
  };

  res.json({
    reject: countBy(
      apps.map((a) => ({ reason: a.rejectReason })),
      'reason'
    ),
    offerDecline: countBy(
      offers.map((o) => ({ reason: o.declineReason })),
      'reason'
    ),
    abandon: countBy(
      onboardings.map((o) => ({ reason: o.abandonReason })),
      'reason'
    ),
  });
});

router.get('/export', authRequired, async (req, res) => {
  const apps = await prisma.application.findMany({
    include: {
      candidate: true,
      job: { include: { org: true, request: true } },
      offers: true,
      onboarding: true,
    },
  });
  const mask = req.user!.role === 'DATA_VIEWER' || req.user!.role === 'INTERVIEWER';
  const rows = apps.map((a) => ({
    applicationId: a.id,
    candidateName: a.candidate.name,
    phone: mask ? '***' : a.candidate.phone,
    email: mask ? '***' : a.candidate.email,
    source: a.candidate.source,
    jobTitle: a.job.title,
    department: a.job.org.name,
    status: a.status,
    enteredAt: a.enteredAt,
    offerStatus: a.offers.find((o) => o.isActive)?.status,
    salary: mask ? null : a.offers.find((o) => o.isActive)?.baseSalary,
    onboardStatus: a.onboarding?.status,
  }));
  await writeAudit(req, '导出流程明细', 'Report', undefined, null, { count: rows.length });
  res.json(rows);
});

// ===== Phase 2 advanced analytics =====

router.get('/efficiency', authRequired, async (_req, res) => {
  const apps = await prisma.application.findMany({
    include: { events: true, job: { include: { org: true, hrOwner: true } } },
  });
  const byOwner: Record<string, { name: string; count: number; avgDays: number; days: number[] }> = {};
  for (const a of apps) {
    const owner = a.job.hrOwner?.name || '未分配';
    if (!byOwner[owner]) byOwner[owner] = { name: owner, count: 0, avgDays: 0, days: [] };
    byOwner[owner].count += 1;
    const enter = a.enteredAt.getTime();
    const end = a.events.find((e) => e.type === 'HIRED' || e.type === 'REJECT')?.createdAt?.getTime() || a.updatedAt.getTime();
    byOwner[owner].days.push(Math.round((end - enter) / 86400000));
  }
  const owners = Object.values(byOwner).map((o) => ({
    ...o,
    avgDays: o.days.length ? Math.round((o.days.reduce((a, b) => a + b, 0) / o.days.length) * 10) / 10 : 0,
  }));
  const alerts = await prisma.alertEvent.count({ where: { resolved: false } });
  const slaHit = apps.filter((a) => !a.slaWarned || a.status === 'HIRED').length;
  res.json({
    byOwner: owners,
    slaAttainment: apps.length ? Math.round((slaHit / apps.length) * 1000) / 10 : 100,
    openAlerts: alerts,
  });
});

router.get('/channel-quality', authRequired, async (_req, res) => {
  const candidates = await prisma.candidate.findMany({
    where: { deleted: false },
    include: { applications: { include: { interviews: true, offers: true } } },
  });
  const map: Record<string, any> = {};
  for (const c of candidates) {
    if (!map[c.source]) map[c.source] = { source: c.source, resumes: 0, valid: 0, interviews: 0, offers: 0, hired: 0 };
    map[c.source].resumes += 1;
    const hasApp = c.applications.length > 0;
    if (hasApp) map[c.source].valid += 1;
    for (const a of c.applications) {
      if (a.interviews.length) map[c.source].interviews += 1;
      if (a.offers.some((o) => ['SENT', 'ACCEPTED', 'DECLINED'].includes(o.status))) map[c.source].offers += 1;
      if (a.status === 'HIRED') map[c.source].hired += 1;
    }
  }
  res.json(
    Object.values(map).map((r: any) => ({
      ...r,
      validRate: r.resumes ? Math.round((r.valid / r.resumes) * 1000) / 10 : 0,
      interviewRate: r.resumes ? Math.round((r.interviews / r.resumes) * 1000) / 10 : 0,
      offerRate: r.resumes ? Math.round((r.offers / r.resumes) * 1000) / 10 : 0,
      hireRate: r.resumes ? Math.round((r.hired / r.resumes) * 1000) / 10 : 0,
    }))
  );
});

router.get('/interview-quality', authRequired, async (_req, res) => {
  const interviews = await prisma.interview.findMany({
    include: { evaluations: true, interviewers: { include: { user: true } }, application: true },
  });
  let timely = 0;
  let totalNeed = 0;
  const scoreDist: number[] = [];
  let disagreements = 0;
  for (const iv of interviews) {
    for (const it of iv.interviewers) {
      totalNeed += 1;
      const ev = iv.evaluations.find((e) => e.interviewerId === it.userId && e.status === 'SUBMITTED');
      if (ev && ev.submittedAt && ev.submittedAt.getTime() - iv.endTime.getTime() <= 48 * 3600000) timely += 1;
      if (ev) {
        try {
          const s = JSON.parse(ev.scores);
          const vals = Object.values(s).filter((v): v is number => typeof v === 'number');
          if (vals.length) scoreDist.push(vals.reduce((a, b) => a + b, 0) / vals.length);
        } catch { /* */ }
      }
    }
    const conclusions = iv.evaluations.filter((e) => e.status === 'SUBMITTED').map((e) => e.conclusion);
    if (conclusions.length >= 2 && new Set(conclusions).size > 1) disagreements += 1;
  }
  res.json({
    timelyRate: totalNeed ? Math.round((timely / totalNeed) * 1000) / 10 : 0,
    avgScore: scoreDist.length ? Math.round((scoreDist.reduce((a, b) => a + b, 0) / scoreDist.length) * 100) / 100 : null,
    disagreementCount: disagreements,
    evaluationCount: scoreDist.length,
  });
});

router.get('/hire-quality', authRequired, async (_req, res) => {
  const records = await prisma.hireQualityRecord.findMany();
  const apps = await prisma.application.findMany({
    where: { status: 'HIRED' },
    include: { candidate: true, job: true, interviews: { include: { evaluations: true } } },
  });
  res.json({
    records,
    hiredCount: apps.length,
    bySource: apps.reduce((acc: Record<string, number>, a) => {
      acc[a.candidate.source] = (acc[a.candidate.source] || 0) + 1;
      return acc;
    }, {}),
    byJob: apps.reduce((acc: Record<string, number>, a) => {
      acc[a.job.title] = (acc[a.job.title] || 0) + 1;
      return acc;
    }, {}),
  });
});

router.post('/hire-quality', authRequired, async (req, res) => {
  const item = await prisma.hireQualityRecord.upsert({
    where: { applicationId: req.body.applicationId },
    create: {
      applicationId: req.body.applicationId,
      employeeNo: req.body.employeeNo,
      probationResult: req.body.probationResult,
      firstYearPerf: req.body.firstYearPerf,
      resigned: !!req.body.resigned,
      resignAt: req.body.resignAt ? new Date(req.body.resignAt) : null,
      notes: req.body.notes,
    },
    update: {
      probationResult: req.body.probationResult,
      firstYearPerf: req.body.firstYearPerf,
      resigned: !!req.body.resigned,
      resignAt: req.body.resignAt ? new Date(req.body.resignAt) : null,
      notes: req.body.notes,
    },
  });
  res.json(item);
});

router.get('/data-service', authRequired, async (req, res) => {
  // Controlled data service for dashboards / Agent — never raw DB bypass
  const metric = String(req.query.metric || 'funnel');
  if (metric === 'funnel') {
    const count = await prisma.application.groupBy({ by: ['status'], _count: true });
    return res.json({ metric, data: count, asOf: new Date().toISOString() });
  }
  if (metric === 'open-jobs') {
    const jobs = await prisma.job.findMany({
      where: { status: 'OPEN' },
      select: { id: true, title: true, headcount: true, hiredCount: true, workLocation: true },
    });
    return res.json({ metric, data: jobs, asOf: new Date().toISOString() });
  }
  res.status(400).json({ message: '不支持的指标，可选 funnel | open-jobs' });
});

export default router;
