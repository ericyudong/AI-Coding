import { config } from './config';

export class RecruitOsClient {
  constructor(private token: string) {}

  private async request<T = any>(method: string, path: string, body?: unknown): Promise<T> {
    const url = `${config.recruitosBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
    const res = await fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.token}`,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error((data as any).message || `RecruitOS ${method} ${path} → ${res.status}`);
    }
    return data as T;
  }

  get<T = any>(path: string) {
    return this.request<T>('GET', path);
  }
  post<T = any>(path: string, body?: unknown) {
    return this.request<T>('POST', path, body);
  }
  patch<T = any>(path: string, body?: unknown) {
    return this.request<T>('PATCH', path, body);
  }

  query(objectType: string, id: string) {
    return this.get(`/api/agent/query/${objectType}/${id}`);
  }
  search(q: string, type?: string) {
    const qs = new URLSearchParams({ q });
    if (type) qs.set('type', type);
    return this.get(`/api/agent/search?${qs}`);
  }
  saveDraft(payload: { type: string; content: string; refType?: string; refId?: string }) {
    return this.post('/api/agent/drafts', { ...payload, agentId: 'hr-agent' });
  }
  proposeAction(payload: { actionKey: string; payload: unknown; idempotencyKey?: string; autoConfirm?: boolean }) {
    return this.post('/api/agent/actions', { ...payload, agentId: 'hr-agent' });
  }
  funnel(jobId?: string) {
    const qs = jobId ? `?jobId=${encodeURIComponent(jobId)}` : '';
    return this.get(`/api/reports/funnel${qs}`);
  }
  overview() {
    return this.get('/api/reports/overview');
  }
  channelRoi() {
    return this.get('/api/reports/channel-quality').catch(() => this.get('/api/reports/channels'));
  }
}

export function clientFromAuthHeader(auth?: string | string[]) {
  const raw = Array.isArray(auth) ? auth[0] : auth;
  if (!raw || !raw.startsWith('Bearer ')) {
    throw new Error('缺少 Authorization Bearer，HR Agent 需以用户身份回调 RecruitOS');
  }
  return new RecruitOsClient(raw.slice(7));
}
