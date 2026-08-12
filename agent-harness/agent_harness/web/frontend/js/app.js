/* ============================================================
   AGENT HARNESS // Control Console — Application Core
   ============================================================ */

const API = {
    status: '/api/status',
    run: '/api/agent/run',
    pause: '/api/agent/pause',
    resume: '/api/agent/resume',
    stop: '/api/agent/stop',
    memoryStats: '/api/memory/stats',
    memorySearch: '/api/memory/search',
    memoryConsolidate: '/api/memory/consolidate',
    telemetryStats: '/api/telemetry/stats',
    sessions: '/api/telemetry/sessions',
    evolutionAnalyze: '/api/evolution/analyze',
};

let ws = null;
let wsConnected = false;
const bootTime = Date.now();
let lastActivity = 0;

/* ---------- Tab navigation ---------- */
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', e => {
        e.preventDefault();
        showTab(item.dataset.tab);
    });
});

function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const tab = document.getElementById(tabId);
    const nav = document.querySelector(`[data-tab="${tabId}"]`);
    if (tab) tab.classList.add('active');
    if (nav) nav.classList.add('active');
    if (tabId === 'memory') loadMemoryStats();
    if (tabId === 'telemetry') loadSessions();
    if (tabId === 'dashboard') refreshStatus();
}

/* ---------- API helper ---------- */
async function api(url, options = {}) {
    try {
        const res = await fetch(url, options);
        return await res.json();
    } catch (e) {
        addLog(`请求失败: ${e.message}`, 'error');
        return null;
    }
}

/* ---------- Status ---------- */
function setAgentLed(state) {
    const led = document.getElementById('agent-led');
    if (!led) return;
    led.className = 'stat-led';
    const s = String(state || '').toLowerCase();
    if (s === 'running') { led.classList.add('led--tel'); led.style.animation = 'blink .7s steps(2) infinite'; }
    else if (s === 'ready') { led.classList.add('led--idle'); led.style.animation = ''; }
    else if (s === 'error') { led.classList.add('led--evo'); led.style.animation = 'blink .4s steps(2) infinite'; }
    else { led.classList.add('led--mem'); led.style.animation = ''; }
}

async function refreshStatus() {
    const status = await api(API.status);
    if (!status) return;

    const agentState = status.agent ? status.agent.state : '--';
    const stateEl = document.getElementById('agent-state');
    if (stateEl && stateEl.textContent !== String(agentState)) {
        stateEl.textContent = agentState;
        stateEl.style.animation = 'none';
        void stateEl.offsetWidth; // reflow to restart animation
        stateEl.style.animation = 'revealUp .4s ease both';
    }
    setAgentLed(agentState);

    const mem = status.memory_stats || {};
    const stm = memCount(mem.short_term);
    const wm = memCount(mem.working);
    const ltm = memCount(mem.long_term);
    setText('memory-count', stm + wm + ltm);

    const tel = status.telemetry_stats || {};
    setText('session-count', tel.total_sessions || 0);
    setText('evolution-count', tel.evolution_runs || status.evolution_runs || 0);

    // Memory tab bars (fill relative to a soft capacity of 100)
    setMemBar('stm-count', 'stm-bar', stm);
    setMemBar('wm-count', 'wm-bar', wm);
    setMemBar('ltm-count', 'ltm-bar', ltm);
}

function memCount(v) {
    if (v == null) return 0;
    if (typeof v === 'number') return v;
    if (typeof v === 'object') return v.size ?? v.active_slots ?? 0;
    return 0;
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el && el.textContent !== String(value)) {
        el.textContent = value;
        el.style.animation = 'none';
        void el.offsetWidth;
        el.style.animation = 'revealUp .35s ease both';
    }
}

function setMemBar(countId, barId, value) {
    setText(countId, value);
    const bar = document.getElementById(barId);
    if (bar) bar.style.width = Math.min(100, value) + '%';
}

/* ---------- Agent controls ---------- */
async function runTask() {
    const input = document.getElementById('task-input');
    const task = input.value.trim();
    if (!task) {
        input.focus();
        input.style.borderColor = 'var(--red-deep)';
        setTimeout(() => input.style.borderColor = '', 900);
        addLog('任务描述为空，已拦截提交', 'error');
        return;
    }

    addLog(`提交任务 → ${task}`);
    kickActivity();

    const container = document.getElementById('result-container');
    container.innerHTML = '<p class="placeholder">▍ 执行中<span class="head-cursor">_</span></p>';

    const res = await api(API.run, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task }),
    });

    if (res && res.success) {
        container.innerHTML =
            `<p><strong>» 任务</strong> ${escapeHtml(task)}</p>` +
            `<p><strong>» 结果</strong> ${escapeHtml(String(res.result))}</p>`;
        addLog(`任务完成 ← ${res.result}`, 'success');
    } else {
        const err = res ? res.error : '请求失败';
        container.innerHTML = `<p class="error">✕ 执行失败: ${escapeHtml(String(err))}</p>`;
        addLog(`任务失败: ${err}`, 'error');
    }
    kickActivity();
    refreshStatus();
}

async function pauseAgent() {
    await api(API.pause, { method: 'POST' });
    addLog('指令已发送: PAUSE', 'error');
    refreshStatus();
}

async function resumeAgent() {
    await api(API.resume, { method: 'POST' });
    addLog('指令已发送: RESUME', 'success');
    refreshStatus();
}

async function stopAgent() {
    await api(API.stop, { method: 'POST' });
    addLog('指令已发送: STOP', 'error');
    refreshStatus();
}

/* ---------- Memory ---------- */
async function loadMemoryStats() {
    const stats = await api(API.memoryStats);
    if (!stats) return;
    setMemBar('stm-count', 'stm-bar', memCount(stats.short_term));
    setMemBar('wm-count', 'wm-bar', memCount(stats.working));
    setMemBar('ltm-count', 'ltm-bar', memCount(stats.long_term));
}

async function searchMemory() {
    const query = document.getElementById('memory-search').value.trim();
    if (!query) return;
    addLog(`检索记忆: "${query}"`);
    const res = await api(`${API.memorySearch}?query=${encodeURIComponent(query)}`);
    const container = document.getElementById('memory-results');
    if (res && res.results && res.results.length > 0) {
        container.innerHTML = res.results.map((r, i) => `
            <div class="memory-item" style="animation-delay:${i * 0.06}s">
                <div class="content">${escapeHtml(JSON.stringify(r.content))}</div>
                <div class="meta">重要性 ${r.importance ?? '--'} · 标签 ${(r.tags || []).join(' / ') || '无'}</div>
            </div>
        `).join('');
        addLog(`命中 ${res.results.length} 条记忆`, 'success');
    } else {
        container.innerHTML = '<p class="placeholder">▍ 未找到相关记忆</p>';
    }
}

async function consolidateMemory() {
    addLog('执行记忆整合...');
    const res = await api(API.memoryConsolidate, { method: 'POST' });
    addLog(`整合完成: ${JSON.stringify(res)}`, 'success');
    loadMemoryStats();
}

/* ---------- Telemetry ---------- */
async function loadSessions() {
    const res = await api(API.sessions);
    const container = document.getElementById('sessions-list');
    if (res && res.sessions && res.sessions.length > 0) {
        container.innerHTML = res.sessions.map((s, i) => `
            <div class="session-item" style="animation-delay:${i * 0.05}s">
                <div>
                    <strong>${escapeHtml(s.task || s.session_id || '--')}</strong>
                    <div class="meta">${escapeHtml(s.start_time || '')} · ${escapeHtml((s.session_id || '').slice(0, 8))}</div>
                </div>
                <div>${s.duration_ms != null ? Number(s.duration_ms).toFixed(1) + ' ms' : 'LIVE'}</div>
            </div>
        `).join('');
        addLog(`已加载 ${res.sessions.length} 条会话记录`, 'success');
    } else {
        container.innerHTML = '<p class="placeholder">▍ 暂无会话记录</p>';
    }
}

/* ---------- Evolution ---------- */
async function triggerEvolution() {
    addLog('触发进化分析引擎...');
    kickActivity();
    const container = document.getElementById('evolution-results');
    container.innerHTML = '<p class="placeholder">▍ 分析中<span class="head-cursor">_</span></p>';

    const res = await api(API.evolutionAnalyze, { method: 'POST' });
    if (res && !res.error) {
        const insights = res.insights || [];
        const suggestions = res.suggestions || [];
        let html = '';
        let idx = 0;
        insights.forEach(i => {
            html += `<div class="insight-card" style="animation-delay:${idx++ * 0.07}s">
                <div class="type">◈ ${escapeHtml(i.type || '洞察')}</div>
                <div class="description">${escapeHtml(i.description || JSON.stringify(i))}</div></div>`;
        });
        suggestions.forEach(s => {
            html += `<div class="insight-card" style="animation-delay:${idx++ * 0.07}s">
                <div class="type">▲ 建议</div>
                <div class="description">${escapeHtml(s.description || JSON.stringify(s))}</div></div>`;
        });
        container.innerHTML = html || '<p class="placeholder">▍ 分析完成，暂无新增洞察</p>';
        addLog('进化分析完成', 'success');
    } else {
        container.innerHTML = `<p class="placeholder" style="color:var(--red)">✕ ${escapeHtml(res ? res.error : '分析失败')}</p>`;
        addLog(`进化分析失败: ${res ? res.error : '未知错误'}`, 'error');
    }
    refreshStatus();
}

/* ---------- Logging ---------- */
function addLog(message, type = '') {
    const container = document.getElementById('log-container');
    if (!container) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    entry.innerHTML = `<span class="log-time">[${time}]</span>${escapeHtml(message)}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
    while (container.children.length > 120) container.removeChild(container.firstChild);
}

/* ---------- Header: clock / uptime / pulse viz ---------- */
function tickClock() {
    const clock = document.getElementById('clock');
    if (clock) clock.textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });

    const up = document.getElementById('uptime');
    if (up) {
        const sec = Math.floor((Date.now() - bootTime) / 1000);
        up.textContent = sec < 60 ? sec + 's' : Math.floor(sec / 60) + 'm ' + (sec % 60) + 's';
    }
}

function kickActivity() { lastActivity = Date.now(); }

function tickPulse() {
    const viz = document.getElementById('pulse-viz');
    if (!viz) return;
    const hot = Date.now() - lastActivity < 2500;
    viz.classList.toggle('hot', hot);
    viz.querySelectorAll('.pulse-bar').forEach(bar => {
        const base = hot ? 35 : 12;
        const span = hot ? 65 : 30;
        bar.style.height = (base + Math.random() * span) + '%';
    });
}

/* ---------- WebSocket ---------- */
function connectWebSocket() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
        ws = new WebSocket(`${protocol}//${location.host}/ws`);
    } catch (e) { return; }

    ws.onopen = () => {
        wsConnected = true;
        const badge = document.getElementById('connection-status');
        badge.innerHTML = '<span class="badge-dot"></span>已连接';
        badge.classList.add('connected');
        addLog('WebSocket 通道建立', 'success');
    };
    ws.onmessage = event => {
        kickActivity();
        try {
            const msg = JSON.parse(event.data);
            if (msg.type === 'task_complete') {
                addLog(`实时推送 ← ${msg.task} ⇒ ${msg.result}`, 'success');
            }
        } catch (e) { /* ignore non-JSON frames */ }
    };
    ws.onclose = () => {
        wsConnected = false;
        const badge = document.getElementById('connection-status');
        badge.innerHTML = '<span class="badge-dot"></span>已断开';
        badge.classList.remove('connected');
        setTimeout(connectWebSocket, 3000);
    };
    ws.onerror = () => { try { ws.close(); } catch (e) {} };
}

/* ---------- Utils ---------- */
function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '\u0026amp;')
        .replace(/</g, '\u0026lt;')
        .replace(/>/g, '\u0026gt;')
        .replace(/"/g, '\u0026quot;')
        .replace(/'/g, '\u0026#39;');
}

/* ---------- Boot ---------- */
document.addEventListener('DOMContentLoaded', () => {
    addLog('控制台内核启动 // AGENT HARNESS v1.0.0');
    refreshStatus();
    connectWebSocket();
    setInterval(refreshStatus, 10000);
    setInterval(tickClock, 1000);
    setInterval(tickPulse, 420);
    tickClock();
});