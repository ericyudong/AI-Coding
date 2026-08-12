import { createBossAdapter, createLiepinAdapter, createSandboxAdapter } from './adapters';
import type { ChannelAdapter } from './types';

const registry: Record<string, ChannelAdapter> = {
  BOSS: createBossAdapter(),
  LIEPIN: createLiepinAdapter(),
  REFERRAL: createSandboxAdapter('REFERRAL', '内推渠道'),
};

export function getChannelAdapter(code: string): ChannelAdapter {
  const key = String(code || '').toUpperCase();
  const adapter = registry[key];
  if (!adapter) {
    // 未知渠道走通用沙箱，避免阻断内部渠道
    return createSandboxAdapter(key || 'UNKNOWN', key || '未知渠道');
  }
  return adapter;
}

export function listChannelAdapters() {
  return Object.values(registry).map((a) => ({ code: a.code, name: a.name }));
}

export async function adaptersHealth() {
  const list = await Promise.all(
    Object.values(registry).map(async (a) => ({
      code: a.code,
      name: a.name,
      ...(await a.health()),
    }))
  );
  return list;
}
