"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.RecruitOsClient = void 0;
exports.clientFromAuthHeader = clientFromAuthHeader;
const config_1 = require("./config");
class RecruitOsClient {
    token;
    constructor(token) {
        this.token = token;
    }
    async request(method, path, body) {
        const url = `${config_1.config.recruitosBaseUrl}${path.startsWith('/') ? path : `/${path}`}`;
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
            throw new Error(data.message || `RecruitOS ${method} ${path} → ${res.status}`);
        }
        return data;
    }
    get(path) {
        return this.request('GET', path);
    }
    post(path, body) {
        return this.request('POST', path, body);
    }
    patch(path, body) {
        return this.request('PATCH', path, body);
    }
    query(objectType, id) {
        return this.get(`/api/agent/query/${objectType}/${id}`);
    }
    search(q, type) {
        const qs = new URLSearchParams({ q });
        if (type)
            qs.set('type', type);
        return this.get(`/api/agent/search?${qs}`);
    }
    saveDraft(payload) {
        return this.post('/api/agent/drafts', { ...payload, agentId: 'hr-agent' });
    }
    proposeAction(payload) {
        return this.post('/api/agent/actions', { ...payload, agentId: 'hr-agent' });
    }
    funnel(jobId) {
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
exports.RecruitOsClient = RecruitOsClient;
function clientFromAuthHeader(auth) {
    const raw = Array.isArray(auth) ? auth[0] : auth;
    if (!raw || !raw.startsWith('Bearer ')) {
        throw new Error('缺少 Authorization Bearer，HR Agent 需以用户身份回调 RecruitOS');
    }
    return new RecruitOsClient(raw.slice(7));
}
