import { compliance } from '../config/compliance';
import type { AdapterResult, ChannelAdapter, OutreachInput, PublishJobInput } from './types';

/** 沙箱适配器：不访问外网，写入可追踪模拟结果 */
export function createSandboxAdapter(code: string, name: string): ChannelAdapter {
  return {
    code,
    name,
    async health() {
      return { ok: true, mode: 'sandbox', detail: '沙箱适配器就绪' };
    },
    async publishJob(input: PublishJobInput): Promise<AdapterResult> {
      return {
        ok: true,
        mode: 'sandbox',
        externalRef: `${code}-SBX-PUB-${Date.now()}`,
        message: `[sandbox] 已模拟发布职位「${input.job.title}」到 ${name}`,
        raw: { title: input.job.title, account: input.account?.accountName },
      };
    },
    async sendGreeting(input: OutreachInput): Promise<AdapterResult> {
      return {
        ok: true,
        mode: 'sandbox',
        externalRef: `${code}-SBX-MSG-${Date.now()}`,
        message: `[sandbox] 已模拟向「${input.candidateName || input.candidateId}」发送打招呼`,
        raw: { message: input.message.slice(0, 200), jobId: input.jobId },
      };
    },
  };
}

async function livePost(apiBase: string, apiKey: string, path: string, body: unknown): Promise<AdapterResult> {
  const url = `${apiBase}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
      'X-RecruitOS-Channel': 'true',
    },
    body: JSON.stringify(body),
  });
  const text = await res.text();
  let raw: any = text;
  try {
    raw = JSON.parse(text);
  } catch {
    /* keep text */
  }
  if (!res.ok) {
    return {
      ok: false,
      mode: 'live',
      message: `外部接口失败 ${res.status}: ${typeof raw === 'string' ? raw.slice(0, 200) : JSON.stringify(raw).slice(0, 200)}`,
      raw,
    };
  }
  return {
    ok: true,
    mode: 'live',
    externalRef: raw?.id || raw?.externalRef || raw?.data?.id || `LIVE-${Date.now()}`,
    message: raw?.message || '外部接口调用成功',
    raw,
  };
}

export function createBossAdapter(): ChannelAdapter {
  const sandbox = createSandboxAdapter('BOSS', 'Boss直聘');
  return {
    code: 'BOSS',
    name: 'Boss直聘',
    async health() {
      if (compliance.mode !== 'live') return sandbox.health();
      if (!compliance.bossEnabled) return { ok: false, mode: 'live', detail: 'CHANNEL_BOSS_ENABLED=false' };
      if (!compliance.boss.apiBase || !compliance.boss.apiKey) {
        return { ok: false, mode: 'live', detail: '缺少 Boss API 配置' };
      }
      return { ok: true, mode: 'live', detail: `已配置 ${compliance.boss.apiBase}` };
    },
    async publishJob(input) {
      if (compliance.mode !== 'live' || !compliance.bossEnabled) return sandbox.publishJob(input);
      return livePost(compliance.boss.apiBase, compliance.boss.apiKey, '/jobs/publish', {
        title: input.job.title,
        location: input.job.workLocation,
        description: input.job.publishCopy || `${input.job.responsibilities || ''}\n${input.job.requirements || ''}`,
        salaryMin: input.job.salaryMin,
        salaryMax: input.job.salaryMax,
        accountExternalId: input.account?.externalId,
        source: 'RecruitOS',
      });
    },
    async sendGreeting(input) {
      if (compliance.mode !== 'live' || !compliance.bossEnabled) return sandbox.sendGreeting(input);
      return livePost(compliance.boss.apiBase, compliance.boss.apiKey, '/messages/greeting', {
        jobId: input.jobId,
        candidateRef: input.externalCandidateRef || input.candidateId,
        message: input.message,
        accountExternalId: input.account?.externalId,
        source: 'RecruitOS',
      });
    },
  };
}

export function createLiepinAdapter(): ChannelAdapter {
  const sandbox = createSandboxAdapter('LIEPIN', '猎聘');
  return {
    code: 'LIEPIN',
    name: '猎聘',
    async health() {
      if (compliance.mode !== 'live') return sandbox.health();
      if (!compliance.liepinEnabled) return { ok: false, mode: 'live', detail: 'CHANNEL_LIEPIN_ENABLED=false' };
      if (!compliance.liepin.apiBase || !compliance.liepin.apiKey) {
        return { ok: false, mode: 'live', detail: '缺少猎聘 API 配置' };
      }
      return { ok: true, mode: 'live', detail: `已配置 ${compliance.liepin.apiBase}` };
    },
    async publishJob(input) {
      if (compliance.mode !== 'live' || !compliance.liepinEnabled) return sandbox.publishJob(input);
      return livePost(compliance.liepin.apiBase, compliance.liepin.apiKey, '/v1/jobs', {
        jobName: input.job.title,
        city: input.job.workLocation,
        jd: input.job.publishCopy || input.job.responsibilities,
        requirements: input.job.requirements,
        salaryRange: [input.job.salaryMin, input.job.salaryMax],
        accountId: input.account?.externalId,
        source: 'RecruitOS',
      });
    },
    async sendGreeting(input) {
      if (compliance.mode !== 'live' || !compliance.liepinEnabled) return sandbox.sendGreeting(input);
      return livePost(compliance.liepin.apiBase, compliance.liepin.apiKey, '/v1/chat/greeting', {
        jobId: input.jobId,
        talentId: input.externalCandidateRef || input.candidateId,
        content: input.message,
        accountId: input.account?.externalId,
        source: 'RecruitOS',
      });
    },
  };
}
