import { prisma } from '../prisma';
import { assertChannelAllowed, compliance } from '../config/compliance';
import { getChannelAdapter } from './registry';

export async function executeChannelPublish(opts: {
  jobId: string;
  channelId: string;
  operatorName?: string;
}) {
  const job = await prisma.job.findUnique({ where: { id: opts.jobId } });
  const channel = await prisma.channel.findUnique({
    where: { id: opts.channelId },
    include: { accounts: true },
  });
  if (!job || !channel) throw new Error('职位或渠道不存在');
  if (job.status !== 'OPEN') throw new Error('仅招聘中职位可对外发布');

  assertChannelAllowed(channel.code, 'publish');
  const adapter = getChannelAdapter(channel.code);
  const account = channel.accounts?.[0] || null;
  const result = await adapter.publishJob({
    channelCode: channel.code,
    job: {
      id: job.id,
      title: job.title,
      workLocation: job.workLocation,
      responsibilities: job.responsibilities,
      requirements: job.requirements,
      publishCopy: job.publishCopy,
      salaryMin: job.salaryMin,
      salaryMax: job.salaryMax,
    },
    account,
  });

  const pub = await prisma.jobChannelPublish.create({
    data: {
      jobId: job.id,
      channelId: channel.id,
      status: result.ok ? 'PUBLISHED' : 'FAILED',
      externalRef: result.externalRef || null,
      resultMsg: `${result.message}${opts.operatorName ? ` · by ${opts.operatorName}` : ''}`,
      publishedAt: result.ok ? new Date() : null,
    },
    include: { channel: true, job: true },
  });

  return { publish: pub, adapterResult: result, mode: compliance.mode };
}

export async function executeExternalOutreach(opts: {
  channelCode: string;
  jobId: string;
  candidateId: string;
  message: string;
  externalCandidateRef?: string;
  operatorName?: string;
}) {
  assertChannelAllowed(opts.channelCode, 'outreach');

  const [job, candidate, channel] = await Promise.all([
    prisma.job.findUnique({ where: { id: opts.jobId } }),
    prisma.candidate.findUnique({ where: { id: opts.candidateId } }),
    prisma.channel.findFirst({
      where: { code: String(opts.channelCode).toUpperCase() },
      include: { accounts: true },
    }),
  ]);
  if (!job) throw new Error('职位不存在');
  if (!candidate) throw new Error('候选人不存在');

  const adapter = getChannelAdapter(opts.channelCode);
  const account = channel?.accounts?.[0] || null;
  const result = await adapter.sendGreeting({
    channelCode: String(opts.channelCode).toUpperCase(),
    jobId: job.id,
    jobTitle: job.title,
    candidateId: candidate.id,
    candidateName: candidate.name,
    message: opts.message,
    account,
    externalCandidateRef: opts.externalCandidateRef,
  });

  const log = await prisma.messageLog.create({
    data: {
      channel: String(opts.channelCode).toUpperCase(),
      templateKey: 'EXTERNAL_OUTREACH',
      toAddr: candidate.phone || candidate.email || candidate.id,
      subject: `寻访打招呼 · ${job.title}`,
      content: opts.message,
      status: result.ok ? 'SENT' : 'FAILED',
      errorMsg: result.ok ? null : result.message,
      refType: 'Candidate',
      refId: candidate.id,
      sentAt: result.ok ? new Date() : null,
    },
  });

  return { messageLog: log, adapterResult: result, mode: compliance.mode };
}
