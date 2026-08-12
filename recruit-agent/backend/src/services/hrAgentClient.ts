const HR_AGENT_URL = (process.env.HR_AGENT_URL || 'http://127.0.0.1:3002').replace(/\/$/, '');

export function getHrAgentUrl() {
  return HR_AGENT_URL;
}

export async function callHrAgent<T = any>(
  path: string,
  opts: { method?: string; token: string; body?: unknown; timeoutMs?: number }
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeoutMs || 120000);
  try {
    const res = await fetch(`${HR_AGENT_URL}${path.startsWith('/') ? path : `/${path}`}`, {
      method: opts.method || 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${opts.token}`,
      },
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: controller.signal,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error((data as any).message || `HR Agent 错误 ${res.status}`);
    }
    return data as T;
  } finally {
    clearTimeout(timer);
  }
}

export async function hrAgentHealth() {
  try {
    const res = await fetch(`${HR_AGENT_URL}/health`);
    if (!res.ok) return { ok: false, url: HR_AGENT_URL };
    return { ok: true, url: HR_AGENT_URL, ...(await res.json()) };
  } catch (e: any) {
    return { ok: false, url: HR_AGENT_URL, message: e.message };
  }
}
