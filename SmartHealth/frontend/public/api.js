/* SmartHealth 控制台 —— API 客户端与小工具（无依赖）。 */

const API = (() => {
  const TOKEN_KEY = 'smarthealth_token';
  const USER_KEY = 'smarthealth_user';

  const REFRESH_KEY = 'smarthealth_refresh';
  const TRACE_KEY = 'smarthealth_last_trace';

  function token() { return localStorage.getItem(TOKEN_KEY) || ''; }
  function refreshToken() { return localStorage.getItem(REFRESH_KEY) || ''; }
  function user() { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null'); } catch { return null; } }
  function lastTrace() { return localStorage.getItem(TRACE_KEY) || ''; }
  function save(accessToken, u, refresh) {
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  }
  function clear() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  // 刷新令牌互斥：多个并发 401 只触发一次刷新，其余等待同一结果，
  // 否则会出现"5 个请求各自去轮换 refresh，4 个把刚拿到的令牌又作废"的连锁失败。
  let refreshInflight = null;

  async function doRefresh() {
    const raw = refreshToken();
    if (!raw) return false;
    if (!refreshInflight) {
      refreshInflight = (async () => {
        try {
          const resp = await fetch('/api/v1/auth/refresh', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: raw }),
          });
          const body = await resp.json().catch(() => null);
          if (!resp.ok || !body || body.code !== 0) { clear(); return false; }
          save(body.data.access_token, body.data.user, body.data.refresh_token);
          return true;
        } catch (_) {
          return false;
        } finally {
          setTimeout(() => { refreshInflight = null; }, 0);
        }
      })();
    }
    return refreshInflight;
  }

  async function raw(method, path, body, isForm) {
    const headers = {};
    const t = token();
    if (t) headers['Authorization'] = 'Bearer ' + t;
    let payloadBody;
    if (isForm) {
      payloadBody = body;                     // FormData：不能设 Content-Type，交给浏览器带 boundary
    } else if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      payloadBody = JSON.stringify(body);
    }
    return fetch(path, { method, headers, body: payloadBody });
  }

  async function request(method, path, body, opts) {
    const options = opts || {};
    let resp = await raw(method, path, body, options.isForm);
    if (resp.status === 401 && !options.isRetry && refreshToken()) {
      const okRefresh = await doRefresh();
      if (okRefresh) resp = await raw(method, path, body, options.isForm);   // 重放一次原请求
    }
    const tid = resp.headers.get('X-Trace-Id');
    if (tid) localStorage.setItem(TRACE_KEY, tid);

    let payload = null;
    const text = await resp.text();
    try { payload = text ? JSON.parse(text) : null; } catch { payload = { message: text }; }
    const data = payload ? payload.data : null;

    if (resp.status === 401) {
      clear();
      const err = new Error((payload && payload.message) || '登录已过期，请重新登录');
      err.status = 401; err.traceId = tid; err.needsLogin = true;
      throw err;
    }
    // 423 = 账号锁定；429 = 限流。两者都必须原样把后端文案给用户，否则用户无从自救。
    if (!resp.ok || (payload && payload.code !== 0 && payload.code !== undefined)) {
      const raw_msg = payload && payload.message;
      const msg = (raw_msg && typeof raw_msg === 'object' && raw_msg.message)
        ? raw_msg.message + (raw_msg.hint ? `（${raw_msg.hint}）` : '') : (raw_msg || `请求失败（HTTP ${resp.status}）`);
      const err = new Error(msg);
      err.status = resp.status;
      err.traceId = tid;
      err.detail = raw_msg;
      throw err;
    }
    return data;
  }

  return {
    token, user, save, clear, refreshToken, lastTrace,
    get: (p) => request('GET', p),
    post: (p, b) => request('POST', p, b || {}),
    patch: (p, b) => request('PATCH', p, b || {}),
    del: (p) => request('DELETE', p),
    /** 文件上传（multipart）。onProgress 用于展示上传进度。 */
    upload: (p, formData, onProgress) => new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', p);
      const t = token();
      if (t) xhr.setRequestHeader('Authorization', 'Bearer ' + t);
      xhr.upload.onprogress = (e) => {
        if (onProgress && e.lengthComputable) onProgress(e.loaded / e.total);
      };
      xhr.onload = () => {
        let body = null;
        try { body = JSON.parse(xhr.responseText); } catch (_) { body = { message: xhr.responseText }; }
        if (xhr.status >= 200 && xhr.status < 300 && body && body.code === 0) resolve(body.data);
        else {
          const m = body && body.message;
          const err = new Error((m && typeof m === 'object' ? m.message : m) || `上传失败（HTTP ${xhr.status}）`);
          err.status = xhr.status; err.detail = m;
          reject(err);
        }
      };
      xhr.onerror = () => reject(new Error('网络错误，上传中断'));
      xhr.send(formData);
    }),
    /** 轮询作业直到终态。返回终态作业；onTick 每次回调用于刷新进度条。 */
    pollJob: async (jobId, onTick, opts) => {
      const o = opts || {};
      const interval = o.intervalMs || 1200;
      const deadline = Date.now() + (o.timeoutMs || 30 * 60 * 1000);
      while (Date.now() < deadline) {
        const p = await request('GET', `/api/v1/jobs/${jobId}/progress`);
        if (onTick) onTick(p);
        if (p.is_terminal) return p;
        await new Promise((r) => setTimeout(r, interval));
      }
      throw new Error('等待作业超时');
    },
    rawUrl: (p) => p,

    /* ------------------------------------------------------------ 事件流
     * 作业进度推送：优先 SSE（断线自动重连 + Last-Event-ID 续传），
     * 连接不可用时（网关拦长连接 / iframe 受限 / 老浏览器）自动退回游标轮询。
     *
     * 为什么两条通道都要有：
     * 院内网关常常拦掉长连接，而"任务进度看不见"是运维最不能接受的失败。
     * 两条通道共用同一份事件语义与游标，切换时上层代码不需要改动。
     */
    openJobEvents(handlers, opts) {
      const h = handlers || {};
      const o = opts || {};
      const pollInterval = o.pollIntervalMs || 2500;
      const state = {
        mode: 'connecting',      // connecting | sse | poll | closed
        cursor: o.afterId || 0,
        transport: '',
        error: '',
      };
      let es = null;
      let timer = null;
      let stopped = false;
      let consecutiveErrors = 0;

      const notifyState = () => { if (h.onState) h.onState({ ...state }); };

      const emit = (event) => {
        if (!event || typeof event.id !== 'number') return;
        if (event.id <= state.cursor) return;      // 去重：SSE 与轮询可能短暂重叠
        state.cursor = event.id;
        if (h.onEvent) h.onEvent(event);
      };

      // ---------------------------------------------------------- 轮询通道
      const startPolling = async () => {
        if (stopped || timer) return;
        state.mode = 'poll';
        notifyState();
        const tick = async () => {
          if (stopped) return;
          try {
            const d = await request('GET',
              `/api/v1/jobs/events?after_id=${state.cursor}&limit=500`);
            (d.events || []).forEach(emit);
            state.error = '';
          } catch (err) {
            state.error = err.message || String(err);
          }
          notifyState();
          if (!stopped) timer = setTimeout(tick, pollInterval);
        };
        tick();
      };

      const stopPolling = () => {
        if (timer) { clearTimeout(timer); timer = null; }
      };

      // ---------------------------------------------------------- SSE 通道
      const startSse = () => {
        if (stopped) return;
        if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
          startPolling();
          return;
        }
        // EventSource 不能自定义请求头，令牌走查询参数；后端同时接受 Bearer。
        const url = `/api/v1/jobs/stream?after_id=${state.cursor}`
          + `&token=${encodeURIComponent(token())}`
          + (o.jobId ? `&job_id=${o.jobId}` : '')
          + (o.jobType ? `&job_type=${encodeURIComponent(o.jobType)}` : '');
        try {
          es = new EventSource(url);
        } catch (err) {
          state.error = String(err);
          startPolling();
          return;
        }

        es.addEventListener('ready', (e) => {
          try {
            const d = JSON.parse(e.data);
            state.transport = d.transport || '';
            if (typeof d.cursor === 'number' && d.cursor > state.cursor) {
              // 服务端确认的游标可能比本地更新（其他标签页刚推过），以服务端为准
              state.cursor = d.cursor;
            }
          } catch (_) { /* 忽略解析失败 */ }
          state.mode = 'sse';
          state.error = '';
          consecutiveErrors = 0;
          stopPolling();
          notifyState();
        });

        es.addEventListener('job', (e) => {
          try { emit(JSON.parse(e.data)); } catch (_) { /* 忽略坏帧 */ }
        });

        es.addEventListener('error', () => {
          // EventSource 自带重连，这里只做状态上报与降级判断。
          // 连续多次失败说明长连接确实建不起来（被网关拦），此时必须退回轮询，
          // 否则前端会陷入"一直重连、一直没有数据"的静默失败。
          consecutiveErrors += 1;
          state.error = '事件流中断，正在重连…';
          notifyState();
          if (consecutiveErrors >= 3) {
            try { es.close(); } catch (_) {}
            es = null;
            startPolling();
          }
        });

        es.addEventListener('open', () => {
          consecutiveErrors = 0;
        });
      };

      startSse();

      return {
        get state() { return { ...state }; },
        close() {
          stopped = true;
          stopPolling();
          if (es) { try { es.close(); } catch (_) {} es = null; }
          state.mode = 'closed';
          notifyState();
        },
      };
    },

    jobEventStats: () => request('GET', '/api/v1/jobs/stream-info'),
  };
})();

/* ------------------------------------------------------------------ 工具 */
const U = {
  esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  },
  num(v, digits) {
    if (v === null || v === undefined || v === '') return '—';
    const n = Number(v);
    if (!isFinite(n)) return U.esc(v);
    return n.toFixed(digits === undefined ? 2 : digits).replace(/\.?0+$/, (m) => (m.includes('.') ? '' : m));
  },
  pct(v, digits) {
    if (v === null || v === undefined) return '—';
    return (Number(v) * 100).toFixed(digits === undefined ? 1 : digits) + '%';
  },
  int(v) { return v === null || v === undefined ? '—' : Number(v).toLocaleString('zh-CN'); },
  bytes(v) {
    if (!v) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let n = Number(v), i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1; }
    return n.toFixed(i === 0 ? 0 : 2) + ' ' + units[i];
  },
  date(s) { return s ? String(s).slice(0, 19).replace('T', ' ') : '—'; },
  tag(text, kind) { return `<span class="tag ${kind || ''}">${U.esc(text)}</span>`; },
  toast(msg, kind) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast ' + (kind || '');
    setTimeout(() => el.classList.add('hidden'), 3600);
  },
  modal(title, html) {
    document.getElementById('modal-title').textContent = title;
    document.getElementById('modal-body').innerHTML = html;
    document.getElementById('modal').classList.remove('hidden');
  },
  closeModal() { document.getElementById('modal').classList.add('hidden'); },
  loading(text) { return `<div class="loading">${U.esc(text || '加载中')}</div>`; },
  empty(text) { return `<div class="empty">${U.esc(text || '暂无数据')}</div>`; },
  kpi(label, value, foot, accent) {
    return `<div class="card tight kpi ${accent ? 'accent' : ''}"><span class="label">${U.esc(label)}</span>`
      + `<span class="value ${String(value).length > 7 ? 'sm' : ''}">${U.esc(value)}</span>`
      + (foot ? `<span class="foot">${U.esc(foot)}</span>` : '') + '</div>';
  },
  bars(items) {
    const max = Math.max(1, ...items.map((i) => Number(i.value) || 0));
    return items.map((i) => {
      const w = Math.max(2, ((Number(i.value) || 0) / max) * 100);
      return `<div class="bar-row"><span class="name">${U.esc(i.name)}</span>`
        + `<span class="bar-track"><span class="bar-fill" style="width:${w.toFixed(1)}%"></span></span>`
        + `<span class="val">${U.esc(i.display !== undefined ? i.display : i.value)}</span></div>`;
    }).join('');
  },
  statusTag(v) {
    const map = {
      done: 'ok', passed: 'ok', succeeded: 'ok', approved: 'ok', online: 'ok', active: 'ok', closed: 'ok', intact: 'ok',
      in_progress: 'sky', running: 'sky', enrolling: 'sky', mitigating: 'sky', submitted: 'sky',
      pending: 'warn', planning: 'warn', preparing: 'warn', at_risk: 'warn', open: 'warn', degraded: 'warn',
      missed: 'danger', failed: 'danger', rejected: 'danger', offline: 'danger', occurred: 'danger', broken: 'danger',
    };
    return U.tag(v || '—', map[v] || '');
  },
  // 生成带分页的表格
  table(columns, rows, opts) {
    const o = opts || {};
    if (!rows || !rows.length) return U.empty(o.emptyText);
    const head = columns.map((c) => `<th${c.width ? ` style="width:${c.width}"` : ''}>${U.esc(c.label)}</th>`).join('');
    const body = rows.map((row) => {
      const tds = columns.map((c) => {
        const raw = c.render ? c.render(row) : row[c.key];
        const val = raw === undefined || raw === null || raw === '' ? '—' : raw;
        return `<td class="${c.align === 'right' ? 'num' : ''}">${c.raw ? val : val}</td>`;
      }).join('');
      return `<tr>${tds}</tr>`;
    }).join('');
    return `<table class="tbl"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
  },
  // 分页控件
  pager(meta, onChange) {
    if (!meta) return '';
    const cur = meta.page, pages = Math.max(1, meta.pages);
    window.__pager = onChange;
    return `<div class="pager">共 ${U.int(meta.total)} 条 · 第 ${cur}/${pages} 页
      <button class="ghost-btn" ${cur <= 1 ? 'disabled' : ''} onclick="window.__pager(${cur - 1})">上一页</button>
      <button class="ghost-btn" ${cur >= pages ? 'disabled' : ''} onclick="window.__pager(${cur + 1})">下一页</button></div>`;
  },
  // 简单折线/ROC 图（内联 SVG，无外部依赖）
  lineChart(points, opts) {
    const o = Object.assign({ width: 520, height: 300, xLabel: '', yLabel: '', diagonal: false }, opts || {});
    if (!points || !points.length) return U.empty('暂无曲线数据');
    const pad = { l: 46, r: 16, t: 16, b: 34 };
    const w = o.width - pad.l - pad.r, h = o.height - pad.t - pad.b;
    const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
    const xmin = Math.min(...xs, o.xMin !== undefined ? o.xMin : 0), xmax = Math.max(...xs, 1);
    const ymin = Math.min(...ys, o.yMin !== undefined ? o.yMin : 0), ymax = Math.max(...ys, 1);
    const X = (v) => pad.l + ((v - xmin) / (xmax - xmin || 1)) * w;
    const Y = (v) => pad.t + h - ((v - ymin) / (ymax - ymin || 1)) * h;
    const path = points.map((p, i) => `${i ? 'L' : 'M'}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`).join(' ');
    let grid = '';
    for (let i = 0; i <= 4; i += 1) {
      const y = pad.t + (h / 4) * i;
      grid += `<line x1="${pad.l}" y1="${y}" x2="${pad.l + w}" y2="${y}" stroke="#eef2f6"/>`;
    }
    const diag = o.diagonal
      ? `<line x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}" stroke="#9fb0bd" stroke-dasharray="4 4"/>` : '';
    return `<svg class="chart" viewBox="0 0 ${o.width} ${o.height}">
      ${grid}${diag}
      <line x1="${pad.l}" y1="${pad.t + h}" x2="${pad.l + w}" y2="${pad.t + h}" stroke="#c9d6e0"/>
      <line x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${pad.t + h}" stroke="#c9d6e0"/>
      <path d="${path}" fill="none" stroke="#08a6f6" stroke-width="2.2"/>
      <text x="${pad.l + w / 2}" y="${o.height - 6}" font-size="11" fill="#667a8c" text-anchor="middle">${U.esc(o.xLabel)}</text>
      <text x="12" y="${pad.t + h / 2}" font-size="11" fill="#667a8c" transform="rotate(-90 12 ${pad.t + h / 2})" text-anchor="middle">${U.esc(o.yLabel)}</text>
    </svg>`;
  },
};
