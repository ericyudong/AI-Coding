/* SmartHealth 控制台 —— 应用外壳：登录、导航、路由。 */

(function () {
  const loginScreen = document.getElementById('login-screen');
  const consoleEl = document.getElementById('console');
  const contentEl = document.getElementById('content');
  const navEl = document.getElementById('nav');
  const crumbsEl = document.getElementById('crumbs');

  function showConsole() {
    loginScreen.classList.add('hidden');
    consoleEl.classList.remove('hidden');
    const u = API.user() || {};
    document.getElementById('whoami').textContent = `${u.real_name || u.username || ''}（${(u.roles || []).join('/')}）`;
    const badge = document.getElementById('deploy-env');
    const env = u.deployment_env || 'research';
    badge.textContent = env === 'product' ? '商用产品环境' : '科研探索环境';
    badge.className = 'pill ' + (env === 'product' ? 'product' : '');
    document.getElementById('env-badge').textContent = env;
    // 权限过滤：无权限的模块直接不显示
    const perms = u.permissions || [];
    const can = (p) => perms.includes('*') || perms.includes(p);
    const modulePerm = {
      overview: 'ops:read', jobs: 'job:read', ingest: 'asset:write', workbench: 'label:write',
      assets: 'asset:read', labels: 'label:read', models: 'model:read',
      pipeline: 'pipeline:run', agents: 'agent:read', evaluation: 'eval:read',
      compliance: 'compliance:read', edge: 'edge:read', registry: 'compliance:read',
      ops: 'ops:read', system: 'system:read',
    };
    navEl.innerHTML = '';
    MODULES.filter((m) => can(modulePerm[m.key] || 'asset:read')).forEach((m) => {
      const item = document.createElement('div');
      item.className = 'nav-item';
      item.dataset.key = m.key;
      item.innerHTML = `<span class="idx">${m.idx}</span><span>${m.label}</span>`;
      item.onclick = () => navigate(m.key);
      navEl.appendChild(item);
    });
    // 页头明确展示「我的数据范围」：避免用户误以为看到的是全院数据（也会主动暴露越权尝试）
    API.get('/api/v1/auth/data-scope').then((scope) => {
      const badge = document.getElementById('scope-badge');
      if (badge) {
        badge.textContent = '数据范围：' + scope.label;
        badge.title = scope.note;
        badge.className = 'pill' + (scope.is_unrestricted ? '' : ' product');
      }
    }).catch(() => {});
    document.getElementById('sidebar-foot').innerHTML =
      'SmartHealth v1.1.0<br>院内私有化 · 数据不出域<br><span id="trace-foot" style="opacity:.7"></span>';
    const hash = (location.hash || '').replace('#/', '');
    navigate(MODULES.some((m) => m.key === hash) ? hash : 'overview');
  }

  async function navigate(key) {
    // 切换模块必须清掉上一个模块的轮询定时器，否则任务中心离开后仍在后台打接口
    (window.__shTimers || []).forEach((t) => clearInterval(t));
    window.__shTimers = [];
    // 事件流连接同样要关：EventSource 不关会一直占着（同源上限通常 6 条），
    // 来回切几次任务中心后就再也建不起新连接，表现为"实时推送突然不工作了"。
    if (window.__shEventStream) {
      try { window.__shEventStream.close(); } catch (_) {}
      window.__shEventStream = null;
    }
    const mod = MODULES.find((m) => m.key === key) || MODULES[0];
    location.hash = '#/' + mod.key;
    navEl.querySelectorAll('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.key === mod.key));
    crumbsEl.textContent = `${mod.idx} ${mod.label}`;
    contentEl.innerHTML = '';
    try {
      await mod.render(contentEl);
    } catch (err) {
      contentEl.innerHTML = `<div class="empty">渲染失败：${U.esc(err.message)}</div>`;
    }
    contentEl.scrollTop = 0;
  }

  /* ------------------------------------------------------------ 登录流程 */
  document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    btn.disabled = true;
    btn.textContent = '登录中…';
    try {
      const data = await API.post('/api/v1/auth/login', {
        username: document.getElementById('username').value.trim(),
        password: document.getElementById('password').value,
      });
      API.save(data.access_token, data.user, data.refresh_token);
      showConsole();
    } catch (err) {
      errEl.textContent = err.message;
    } finally {
      btn.disabled = false;
      btn.textContent = '登录';
    }
  });

  document.getElementById('logout').onclick = async () => {
    try { await API.post('/api/v1/auth/logout'); } catch (_) { /* 忽略 */ }
    API.clear();
    location.reload();
  };

  document.getElementById('modal-close').onclick = U.closeModal;
  document.getElementById('modal').addEventListener('click', (e) => {
    if (e.target.id === 'modal') U.closeModal();
  });

  window.addEventListener('hashchange', () => {
    if (consoleEl.classList.contains('hidden')) return;
    const key = (location.hash || '').replace('#/', '');
    if (key && MODULES.some((m) => m.key === key)) navigate(key);
  });

  /* ------------------------------------------------------------ 启动 */
  (async function boot() {
    if (!API.token()) { loginScreen.classList.remove('hidden'); return; }
    try {
      const me = await API.get('/api/v1/auth/me');
      API.save(API.token(), {
        id: me.id, username: me.username, real_name: me.real_name,
        department: me.department, roles: me.roles, permissions: me.permissions,
        deployment_env: me.deployment_env, org_code: me.org_code,
        site_code: me.site_code, data_scope: me.data_scope,
      }, API.refreshToken());
      showConsole();
    } catch (_) {
      API.clear();
      loginScreen.classList.remove('hidden');
    }
  })();
})();
