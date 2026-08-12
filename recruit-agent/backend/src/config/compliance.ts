/**
 * 渠道合规开关（RecruitOS）
 * - sandbox：不调用真实外部平台，仅模拟并写审计
 * - live：调用配置好的外部 API（仍默认需人工确认）
 */
import '../loadEnv';

function bool(v: string | undefined, def = false) {
  if (v === undefined || v === '') return def;
  return ['1', 'true', 'yes', 'on'].includes(String(v).toLowerCase());
}

export type ChannelMode = 'sandbox' | 'live';

export const compliance = {
  /** 全局模式 */
  mode: (process.env.CHANNEL_MODE === 'live' ? 'live' : 'sandbox') as ChannelMode,
  /** 外部触达总开关（寻访打招呼等） */
  externalOutreachEnabled: bool(process.env.EXTERNAL_OUTREACH_ENABLED, false),
  /** 外部动作是否必须人工确认（默认强制） */
  requireHumanConfirm: bool(process.env.CHANNEL_REQUIRE_HUMAN_CONFIRM, true),
  /** 各渠道开关 */
  bossEnabled: bool(process.env.CHANNEL_BOSS_ENABLED, false),
  liepinEnabled: bool(process.env.CHANNEL_LIEPIN_ENABLED, false),
  /** 真实通道凭证（仅 live 使用） */
  boss: {
    apiBase: (process.env.CHANNEL_BOSS_API_BASE || '').replace(/\/$/, ''),
    apiKey: process.env.CHANNEL_BOSS_API_KEY || '',
  },
  liepin: {
    apiBase: (process.env.CHANNEL_LIEPIN_API_BASE || '').replace(/\/$/, ''),
    apiKey: process.env.CHANNEL_LIEPIN_API_KEY || '',
  },
};

export function channelEnabled(code: string) {
  const c = String(code || '').toUpperCase();
  if (c === 'BOSS') return compliance.bossEnabled || compliance.mode === 'sandbox';
  if (c === 'LIEPIN') return compliance.liepinEnabled || compliance.mode === 'sandbox';
  // 内推等非外部渠道默认允许
  return true;
}

export function assertChannelAllowed(code: string, action: 'publish' | 'outreach') {
  const c = String(code || '').toUpperCase();
  if (action === 'outreach' && !compliance.externalOutreachEnabled && compliance.mode === 'live') {
    throw new Error('合规拦截：EXTERNAL_OUTREACH_ENABLED 未开启，禁止 live 外部触达');
  }
  if ((c === 'BOSS' || c === 'LIEPIN') && compliance.mode === 'live') {
    if (c === 'BOSS' && !compliance.bossEnabled) throw new Error('合规拦截：Boss 渠道未启用（CHANNEL_BOSS_ENABLED）');
    if (c === 'LIEPIN' && !compliance.liepinEnabled) throw new Error('合规拦截：猎聘渠道未启用（CHANNEL_LIEPIN_ENABLED）');
    if (c === 'BOSS' && (!compliance.boss.apiBase || !compliance.boss.apiKey)) {
      throw new Error('合规拦截：Boss live 缺少 CHANNEL_BOSS_API_BASE / CHANNEL_BOSS_API_KEY');
    }
    if (c === 'LIEPIN' && (!compliance.liepin.apiBase || !compliance.liepin.apiKey)) {
      throw new Error('合规拦截：猎聘 live 缺少 CHANNEL_LIEPIN_API_BASE / CHANNEL_LIEPIN_API_KEY');
    }
  }
  if (!channelEnabled(c) && compliance.mode === 'live') {
    throw new Error(`合规拦截：渠道 ${c} 未启用`);
  }
}

export function complianceSnapshot() {
  return {
    mode: compliance.mode,
    externalOutreachEnabled: compliance.externalOutreachEnabled,
    requireHumanConfirm: compliance.requireHumanConfirm,
    channels: {
      BOSS: {
        enabled: compliance.bossEnabled || compliance.mode === 'sandbox',
        configured: Boolean(compliance.boss.apiBase && compliance.boss.apiKey),
      },
      LIEPIN: {
        enabled: compliance.liepinEnabled || compliance.mode === 'sandbox',
        configured: Boolean(compliance.liepin.apiBase && compliance.liepin.apiKey),
      },
    },
    notes: [
      'sandbox 模式不调用真实外部接口，可安全联调',
      'live 模式需显式开启渠道开关并配置 API 凭证',
      'PUBLISH_CHANNEL / EXTERNAL_OUTREACH 默认高风险，须人工确认后执行',
    ],
  };
}
