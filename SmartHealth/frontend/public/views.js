/* SmartHealth 控制台 —— 视图层。
 *
 * 12 个业务模块 + 1 个总览。每个模块由若干「面板」组成：
 *   - listPanel()  通用列表（搜索 + 过滤 + 分页 + 详情弹窗），覆盖全部 CRUD 资源
 *   - 自定义面板    面向决策的关键视图（许可体检、Agent 会话、评测 ROC、注册甘特、风险矩阵、运营看板）
 */

/* =============================================================== 通用列表面板 */
function listPanel(cfg) {
  const state = { page: 1, size: cfg.pageSize || 20, search: '', filters: {} };
  const el = document.createElement('div');
  el.className = 'panel';
  el.innerHTML = '<div class="loading">加载中</div>';

  function query() {
    const p = new URLSearchParams();
    p.set('page', state.page);
    p.set('page_size', state.size);
    if (state.search) p.set('search', state.search);
    Object.entries(state.filters).forEach(([k, v]) => { if (v !== '' && v !== null) p.set(k, v); });
    return `${cfg.endpoint}?${p.toString()}`;
  }

  async function load() {
    el.innerHTML = '<div class="loading">加载中</div>';
    try {
      const data = await API.get(query());
      const items = data.items || [];
      const meta = data.meta || { total: items.length, page: 1, pages: 1, page_size: state.size };
      const filterHtml = (cfg.filters || []).map((f) => {
        if (f.type === 'select') {
          const opts = (f.options || []).map((o) => {
            const val = typeof o === 'string' ? o : o.value;
            const lab = typeof o === 'string' ? o : o.label;
            return `<option value="${U.esc(val)}" ${state.filters[f.key] === val ? 'selected' : ''}>${U.esc(lab)}</option>`;
          }).join('');
          return `<select data-filter="${U.esc(f.key)}"><option value="">${U.esc(f.label)}（全部）</option>${opts}</select>`;
        }
        return `<input type="text" data-filter="${U.esc(f.key)}" placeholder="${U.esc(f.label)}"
                 value="${U.esc(state.filters[f.key] || '')}" />`;
      }).join('');

      el.innerHTML = `
        <div class="toolbar">
          ${cfg.searchable === false ? '' : `<input type="text" id="q" placeholder="搜索…" value="${U.esc(state.search)}" />`}
          ${filterHtml}
          <button class="btn ghost" id="reload">刷新</button>
          <span class="spacer"></span>
          <span class="muted" style="font-size:12px;color:#667a8c">共 ${U.int(meta.total)} 条</span>
        </div>
        <div id="tbl"></div>
        <div id="pg"></div>`;

      document.getElementById('tbl').innerHTML = U.table(cfg.columns, items, { emptyText: cfg.emptyText });
      document.getElementById('pg').innerHTML = U.pager(meta, (p) => { state.page = p; load(); });

      const q = el.querySelector('#q');
      if (q) {
        let timer = null;
        q.addEventListener('input', () => {
          clearTimeout(timer);
          timer = setTimeout(() => { state.search = q.value.trim(); state.page = 1; load(); }, 320);
        });
        q.addEventListener('keydown', (e) => { if (e.key === 'Enter') { state.search = q.value.trim(); state.page = 1; load(); } });
      }
      el.querySelectorAll('[data-filter]').forEach((node) => {
        const evt = node.tagName === 'SELECT' ? 'change' : 'change';
        node.addEventListener(evt, () => {
          const key = node.getAttribute('data-filter');
          if (node.value) state.filters[key] = node.value; else delete state.filters[key];
          state.page = 1; load();
        });
      });
      el.querySelector('#reload').onclick = load;

      if (cfg.onRow) {
        el.querySelectorAll('table.tbl tbody tr').forEach((tr, i) => {
          tr.style.cursor = 'pointer';
          tr.addEventListener('click', () => cfg.onRow(items[i], load));
        });
      }
    } catch (err) {
      el.innerHTML = `<div class="empty">加载失败：${U.esc(err.message)}</div>`;
    }
  }

  el.reload = load;
  load();
  return el;
}

/* =============================================================== 00 概览 */
async function renderOverview(root) {
  root.innerHTML = U.loading('加载运营看板');
  try {
    const d = await API.get('/api/v1/ops/dashboard');
    const k = d.kpi || {};
    const head = d.headline || {};
    root.innerHTML = `
      <div class="note" style="margin-bottom:16px">
        ${U.esc(head.narrative || '把多年积累、已由医生标注的病理切片，转化为可注册、可交付、可持续迭代的医疗 AI 能力。')}
      </div>
      <div class="grid c4" style="margin-bottom:16px">
        ${U.kpi('数据资产 / 切片', `${U.int(k.asset_count)} / ${U.int(k.slide_count)}`, '含已标注切片 ' + U.int(k.annotated_slide_count), true)}
        ${U.kpi('院内 AUROC', U.num(k.model_auroc, 4), '外部验证 ' + U.num(k.external_auroc, 4))}
        ${U.kpi('Agent 拒识率', U.pct(k.agent_reject_rate), `会话 ${U.int(k.agent_session_count)} 次`)}
        ${U.kpi('注册就绪度', U.pct((d.readiness || {}).readiness_score), `里程碑 ${U.int(k.milestone_done)}/${U.int(k.milestone_total)}`)}
      </div>
      <div class="grid c2">
        <div class="card"><h4>关键指标</h4>
          ${U.bars([
            { name: '特征库就绪', value: k.feature_ready_count || 0, display: U.int(k.feature_ready_count) },
            { name: '标注记录', value: k.annotation_count || 0, display: U.int(k.annotation_count) },
            { name: '审计记录', value: k.audit_record_count || 0, display: U.int(k.audit_record_count) },
            { name: '在线边缘节点', value: k.edge_online_count || 0, display: U.int(k.edge_online_count) },
          ])}
        </div>
        <div class="card"><h4>风控与合规</h4>
          <div class="muted" style="margin-bottom:8px">注册就绪度：${U.pct((d.readiness || {}).readiness_score)}
            （${U.int((d.readiness || {}).passed_count)}/${U.int((d.readiness || {}).total_count)} 项通过）</div>
          ${((d.readiness || {}).blocked_review_labels || []).length
            ? `<div class="chips">${(d.readiness.blocked_review_labels || []).map((s) => `<span class="chip danger">${U.esc(s)}</span>`).join('')}</div>`
            : '<div class="chips"><span class="chip ok">无阻断审评关口</span></div>'}
          <div class="muted" style="margin-top:12px">前置风险 ${U.int((d.risk || {}).frontloaded_count)} 项 ·
            最高风险分 ${U.num((d.risk || {}).max_risk_score, 0)}</div>
        </div>
      </div>
      <div class="grid c2" style="margin-top:14px">
        <div class="card"><h4>模型与流水线</h4>
          <pre class="mono" style="white-space:pre-wrap;color:#34495a;margin:0">${U.esc(JSON.stringify(d.pipeline || {}, null, 2).slice(0, 900))}</pre>
        </div>
        <div class="card"><h4>标签体系覆盖</h4>
          <pre class="mono" style="white-space:pre-wrap;color:#34495a;margin:0">${U.esc(JSON.stringify(d.coverage || {}, null, 2).slice(0, 900))}</pre>
        </div>
      </div>`;
  } catch (err) {
    root.innerHTML = `<div class="empty">概览加载失败：${U.esc(err.message)}</div>`;
  }
}

/* =============================================================== 02 数据资产 */
function renderAssets(root) {
  const tabs = document.createElement('div');
  tabs.innerHTML = `
    <div class="grid c4" id="asset-kpi" style="margin-bottom:16px">${U.loading('')}</div>
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card"><h4>按中心分布</h4><div id="asset-site"></div></div>
      <div class="card"><h4>按染色类型</h4><div id="asset-stain"></div></div>
    </div>
    <div id="asset-list"></div>`;
  root.appendChild(tabs);

  API.get('/api/v1/assets/overview').then((o) => {
    document.getElementById('asset-kpi').innerHTML =
      U.kpi('数据资产', U.int(o.asset_count), `切片区 ${U.int(o.slide_count)}`, true)
      + U.kpi('患者（去标识）', U.int(o.patient_count), `已标注切片 ${U.int(o.annotated_slide_count)}`)
      + U.kpi('阳性切片', U.int(o.positive_slide_count), `占比 ${U.pct(o.slide_count ? o.positive_slide_count / o.slide_count : 0)}`)
      + U.kpi('影像总量', U.bytes(o.total_bytes), `${o.total_tb} TB（合成估算）`);
    document.getElementById('asset-site').innerHTML = U.bars(Object.entries(o.by_site || {}).map(([k, v]) => ({
      name: k, value: v.slides, display: `${v.slides}（阳 ${v.positive}）`,
    })));
    document.getElementById('asset-stain').innerHTML = U.bars(Object.entries(o.by_staining || {}).map(([k, v]) => ({ name: k, value: v, display: String(v) })));
  }).catch((e) => { document.getElementById('asset-kpi').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });

  document.getElementById('asset-list').appendChild(listPanel({
    endpoint: '/api/v1/slides',
    columns: [
      { key: 'code', label: '切片编号' },
      { key: 'case_no', label: '病例号' },
      { key: 'organ', label: '器官' },
      { key: 'cancer_type', label: '病种' },
      { key: 'staining', label: '染色' },
      { key: 'site_code', label: '中心' },
      { key: 'has_lesion', label: '标签', render: (r) => (r.has_lesion ? U.tag('阳性', 'danger') : U.tag('阴性', 'ok')) },
      { key: 'split', label: '划分', render: (r) => U.tag(r.split || '—', 'sky') },
      { key: 'tile_count', label: '图块数', align: 'right', render: (r) => U.int(r.tile_count) },
    ],
    filters: [
      { key: 'site_code', label: '中心' },
      { key: 'staining', label: '染色' },
      { key: 'split', label: '划分', type: 'select', options: ['train', 'val', 'test', 'external'] },
      { key: 'has_lesion', label: '是否阳性', type: 'select', options: [{ value: 'true', label: '阳性' }, { value: 'false', label: '阴性' }] },
    ],
    onRow: (row) => openSlideDetail(row),
  }));
}

async function openSlideDetail(row) {
  U.modal(`切片 ${row.code}`, U.loading('加载切片详情'));
  try {
    const d = await API.get(`/api/v1/slides/${row.id}/detail`);
    const layers = d.annotation_by_layer || {};
    const layerNames = { case: '病例级', slide: '切片级', region: '区域级', cell: '细胞级', qc: '质控层' };
    let annHtml = '';
    const keys = Object.keys(layers);
    annHtml = keys.length
      ? keys.map((k) => `<div style="margin-bottom:10px"><strong>${U.esc(layerNames[k] || k)}</strong>
          <div class="chips" style="margin-top:6px">${layers[k].map((a) => `<span class="chip">${U.esc(a.schema_code)}：${U.esc(a.value ?? '—')}</span>`).join('')}</div></div>`).join('')
      : '<div class="muted">该切片尚未录入标注</div>';

    const pred = d.prediction;
    const regions = d.attention_regions || [];
    U.modal(`切片 ${row.code} · ${row.case_no || ''}`, `
      <div class="grid c2" style="margin-bottom:14px">
        <div>
          <div class="grid c2">
            ${U.kpi('病例号', row.case_no || '—')}
            ${U.kpi('中心', row.site_code || '—')}
            ${U.kpi('染色 / 放大', `${row.staining} / ${row.magnification || '—'}`)}
            ${U.kpi('物理分辨率', `${row.mpp} µm/px`)}
          </div>
        </div>
        <div style="background:#061f32;border-radius:10px;overflow:hidden;min-height:200px">
          <img src="/api/v1/slides/${row.id}/preview?level=2&overlay=true" style="width:100%;display:block"
               onerror="this.parentNode.innerHTML='<div style=\\'color:#9fb0bd;padding:24px;font-size:12px\\'>预览图尚未生成，请先执行特征预计算</div>'" />
        </div>
      </div>
      <h4 style="margin:14px 0 8px">四层标签</h4>${annHtml}
      <h4 style="margin:14px 0 8px">模型预测</h4>
      ${pred ? `<div class="grid c4">${U.kpi('结论', pred.verdict || '—')}${U.kpi('校准概率', U.num(pred.calibrated_probability, 4))}${U.kpi('置信度', (pred.confidence_level || '—').toUpperCase())}${U.kpi('是否拒识', pred.rejected ? '是' : '否')}</div>`
             : '<div class="muted">该切片尚无推理结果</div>'}
      ${regions.length ? `<h4 style="margin:14px 0 8px">注意力热区（前 ${Math.min(regions.length, 8)} 个，即证据位置）</h4>
        ${U.table([
          { key: 'rank', label: '#', width: '50px' },
          { key: 'level', label: '倍率层级' },
          { key: 'x', label: 'X', align: 'right' }, { key: 'y', label: 'Y', align: 'right' },
          { key: 'width', label: 'W', align: 'right' }, { key: 'height', label: 'H', align: 'right' },
          { key: 'attention', label: '注意力', align: 'right', render: (r) => U.num(r.attention, 4) },
          { key: 'tissue_ratio', label: '组织占比', align: 'right', render: (r) => U.pct(r.tissue_ratio) },
        ], regions.slice(0, 8))}` : ''}
    `);
  } catch (err) {
    U.modal('加载失败', `<div class="empty">${U.esc(err.message)}</div>`);
  }
}

/* =============================================================== 03 标签体系 */
function renderLabels(root) {
  root.innerHTML = '<div id="label-top"></div><div id="label-list" style="margin-top:16px"></div>';
  API.get('/api/v1/labels/overview').then((o) => {
    const cov = o.coverage || {};
    const sop = o.sop || {};
    const layers = cov.by_layer || {};
    const layerOrder = ['case', 'slide', 'region', 'cell', 'qc'];
    document.getElementById('label-top').innerHTML = `
      <div class="grid c4" style="margin-bottom:14px">
        ${U.kpi('标签定义', U.int(cov.schema_total), '四层 + 质控层', true)}
        ${U.kpi('标注记录', U.int(o.annotation_total), `覆盖 ${U.int(cov.slide_total)} 张切片`)}
        ${U.kpi('SOP 已审核', `${U.int(sop.approved_count)}/${U.int(sop.sop_total)}`, `仲裁 ${U.int(sop.arbitration_resolved)} 已裁 / ${U.int(sop.arbitration_open)} 待裁`)}
        ${U.kpi('质控通过率', U.pct(o.qc_pass_rate), `质控记录 ${U.int(o.qc_total)} 条`)}
      </div>
      <div class="grid c2">
        <div class="card"><h4>分层覆盖率（分母仅计声明范围内的 H&E 切片）</h4>
          ${U.bars(layerOrder.filter((k) => layers[k]).map((k) => ({
            name: layers[k].label || k,
            value: (layers[k].coverage_rate || 0) * 100,
            display: `${U.pct(layers[k].coverage_rate)} · ${U.int(layers[k].schema_count)} 项`,
          })))}
          <div class="muted" style="margin-top:6px">${U.esc(cov.note || '')}</div>
        </div>
        <div class="card"><h4>注册必备标签缺口</h4>
          ${(cov.registration_gaps || []).length
            ? `<div class="chips">${cov.registration_gaps.map((g) => `<span class="chip danger">${U.esc(g.code)} ${U.esc(g.name)}（缺 ${U.int(g.missing)}）</span>`).join('')}</div>`
            : '<div class="chips"><span class="chip ok">注册必备标签已全覆盖</span></div>'}
          <div class="muted" style="margin-top:8px">注册必备标签 ${U.int(cov.registration_required_count)} 项 ·
            ${cov.registration_ready ? '可支撑「数据可溯源」应答' : '将阻断注册申报（对应审评问一）'}</div>
          <div class="note" style="margin-top:10px">${U.esc(sop.note || '')}</div>
        </div>
      </div>`;
  }).catch((e) => { document.getElementById('label-top').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });

  document.getElementById('label-list').appendChild(listPanel({
    endpoint: '/api/v1/labels/schemas',
    columns: [
      { key: 'code', label: '编码' },
      { key: 'name', label: '标签名称' },
      { key: 'layer', label: '层级', render: (r) => U.tag(({ case: '病例级', slide: '切片级', region: '区域级', cell: '细胞级', qc: '质控层' })[r.layer] || r.layer, 'sky') },
      { key: 'value_type', label: '取值类型' },
      { key: 'unit', label: '单位' },
      { key: 'snomed_code', label: 'SNOMED CT' },
      { key: 'required_for_training', label: '训练必备', render: (r) => (r.required_for_training ? U.tag('是', 'sky') : '—') },
      { key: 'required_for_registration', label: '注册必备', render: (r) => (r.required_for_registration ? U.tag('是', 'danger') : '—') },
      { key: 'description', label: '说明' },
    ],
    filters: [{ key: 'layer', label: '层级', type: 'select', options: ['case', 'slide', 'region', 'cell', 'qc'] }],
  }));
}

/* =============================================================== 04 模型与算力 */
function renderModels(root) {
  root.innerHTML = `
    <div id="model-license" class="grid c2" style="margin-bottom:16px"></div>
    <div id="model-list"></div>`;
  API.get('/api/v1/models/encoders/license-audit').then((a) => {
    const block = (arr, kind, title) => `
      <div class="card"><h4>${U.esc(title)}（${arr.length}）</h4>
        ${arr.length ? arr.map((e) => `<div style="display:flex;justify-content:space-between;padding:7px 0;border-bottom:1px dashed var(--line)">
          <span><strong>${U.esc(e.name)}</strong> <span class="mono" style="color:#667a8c">${U.esc(e.code)}</span></span>
          <span>${U.tag(e.license_name, kind)}${e.is_self_developed ? U.tag('自研', 'ok') : ''}</span></div>`).join('')
        : '<div class="muted">无</div>'}
      </div>`;
    document.getElementById('model-license').innerHTML =
      block(a.allowed || [], 'ok', `可商用许可（当前环境 ${a.deployment_env} 可用）`)
      + block(a.blocked || [], 'danger', '非商用 / 受限许可（商用主线不可用）');
  }).catch((e) => { document.getElementById('model-license').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });

  document.getElementById('model-list').appendChild(listPanel({
    endpoint: '/api/v1/models/versions',
    columns: [
      { key: 'semver', label: '版本号' },
      { key: 'name', label: '名称' },
      { key: 'encoder_code', label: '编码器' },
      {
        key: 'metrics_json', label: 'AUROC（院内 / 外部）',
        render: (r) => {
          let m = {};
          try { m = JSON.parse(r.metrics_json || '{}'); } catch (_) { m = {}; }
          const a = m.auroc !== undefined ? m.auroc : (m.internal_auroc !== undefined ? m.internal_auroc : null);
          const b = m.external_auroc !== undefined ? m.external_auroc : null;
          return `${U.num(a, 4)} / ${U.num(b, 4)}`;
        },
      },
      { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
      { key: 'locked', label: '锁定', render: (r) => (r.locked ? U.tag('已锁定', 'sky') : '—') },
      { key: 'is_registration_candidate', label: '注册候选', render: (r) => (r.is_registration_candidate ? U.tag('是', 'sky') : '—') },
      { key: 'param_count', label: '参数量', align: 'right', render: (r) => (r.param_count ? (r.param_count / 1e6).toFixed(1) + 'M' : '—') },
      { key: 'created_at', label: '创建时间', render: (r) => U.date(r.created_at) },
    ],
    filters: [{ key: 'status', label: '状态', type: 'select', options: ['draft', 'validated', 'locked', 'deprecated'] }],
  }));
}

/* =============================================================== 05 推理流水线 */
function renderPipeline(root) {
  root.innerHTML = `
    <div id="pipe-top" style="margin-bottom:16px"></div>
    <div class="grid c3" style="margin-bottom:16px">
      <div class="card"><h4>按编码器特征库</h4><div id="pipe-enc"></div></div>
      <div class="card"><h4>推理决策分布</h4><div id="pipe-dec"></div></div>
      <div class="card"><h4>置信度分布</h4><div id="pipe-conf"></div></div>
    </div>
    <div id="pipe-list"></div>`;
  API.get('/api/v1/inference/overview').then((o) => {
    document.getElementById('pipe-top').innerHTML = `<div class="grid c4">
      ${U.kpi('切片总数', U.int(o.slide_total), '全部纳入流水线')}
      ${U.kpi('特征就绪', U.int(o.stage_a_feature_ready), `覆盖率 ${U.pct(o.feature_coverage)}`, true)}
      ${U.kpi('已推理', U.int(o.inferred_slide_count), '含拒识')}
      ${U.kpi('Agent 会话', U.int(o.agent_session_count), '多模态探索线')}
    </div>
    <div class="card" style="margin-top:14px"><h4>四阶段完成度</h4>
      ${U.bars((o.stages || []).map((s) => ({ name: `${s.key} ${s.name}`, value: s.total ? (s.done / s.total) * 100 : 0, display: `${U.int(s.done)}/${U.int(s.total)}` })))}
      <div class="muted" style="margin-top:6px">Stage A 一次性把切片转成可复用特征库，后续训练/推理/评测/Agent 全部复用同一份特征，边际算力成本极低。</div>
    </div>`;
  }).catch(() => {});
  API.get('/api/v1/features/overview').then((o) => {
    document.getElementById('pipe-enc').innerHTML = U.bars((o.by_encoder || []).map((e) => ({ name: e.encoder_code, value: e.slide_count, display: `${e.slide_count} 张` })));
  }).catch(() => {});
  API.get('/api/v1/inference/summary').then((o) => {
    document.getElementById('pipe-dec').innerHTML = U.bars(Object.entries(o.by_decision || {}).map(([k, v]) => ({ name: k, value: v, display: String(v) })))
      + `<div class="muted" style="margin-top:6px">拒识率 ${U.pct(o.reject_rate)}</div>`;
    document.getElementById('pipe-conf').innerHTML = U.bars(Object.entries(o.by_confidence || {}).map(([k, v]) => ({ name: k, value: v, display: String(v) })))
      + `<div class="muted" style="margin-top:6px">注意力热区命中率 ${U.pct(o.attention_hit_rate)}（${U.int(o.attention_lesion_overlap)}/${U.int(o.attention_region_total)}）</div>`;
  }).catch(() => {});
  document.getElementById('pipe-list').appendChild(listPanel({
    endpoint: '/api/v1/inference/predictions',
    columns: [
      { key: 'slide_code', label: '切片' },
      { key: 'model_version_label', label: '模型版本' },
      { key: 'probability', label: '原始概率', align: 'right', render: (r) => U.num(r.probability, 4) },
      { key: 'calibrated_probability', label: '校准概率', align: 'right', render: (r) => U.num(r.calibrated_probability, 4) },
      { key: 'decision', label: '结论', render: (r) => U.tag(r.decision || '—', r.decision === 'positive' ? 'danger' : 'ok') },
      { key: 'confidence_level', label: '置信度' },
      { key: 'rejected', label: '拒识', render: (r) => (r.rejected ? U.tag('拒识', 'warn') : '—') },
      { key: 'elapsed_ms', label: '耗时(ms)', align: 'right' },
    ],
    onRow: async (row) => {
      U.modal(`预测详情 · ${row.slide_code}`, U.loading());
      try {
        const d = await API.get(`/api/v1/inference/predictions/${row.id}/detail`);
        U.modal(`预测详情 · ${row.slide_code}`, `
          <div class="grid c4" style="margin-bottom:12px">
            ${U.kpi('原始概率', U.num(d.probability, 4))}${U.kpi('校准概率', U.num(d.calibrated_probability, 4))}
            ${U.kpi('结论', d.decision || '—')}${U.kpi('置信度', (d.confidence_level || '—').toUpperCase())}
          </div>
          <div style="background:#061f32;border-radius:10px;overflow:hidden">
            <img src="/api/v1/inference/predictions/${d.id}/heatmap" style="width:100%;display:block"
                 onerror="this.parentNode.innerHTML='<div style=\\'color:#9fb0bd;padding:24px;font-size:12px\\'>热力图未生成</div>'" />
          </div>
          <div class="note" style="margin-top:12px">注意力热区即模型给出结论的证据位置，可直接对应到切片坐标。</div>`);
      } catch (e) { U.modal('加载失败', U.esc(e.message)); }
    },
  }));
}

/* =============================================================== 06 Agent */
function renderAgents(root) {
  root.innerHTML = `
    <div class="grid c4" id="agent-kpi" style="margin-bottom:16px"></div>
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card"><h4>五智能体架构</h4><div id="agent-arch"></div></div>
      <div class="card"><h4>运行一次分析</h4>
        <div class="muted" style="margin-bottom:8px">选一张切片，触发「编排 → 分诊 → 导航 → 描述 → 诊断」全链路，所有结论强制绑定证据。</div>
        <div class="toolbar"><select id="agent-slide" style="min-width:240px"></select>
        <button class="btn sky" id="agent-run">运行 Agent 分析</button></div>
        <div id="agent-run-hint" class="muted"></div>
      </div>
    </div>
    <div id="agent-list"></div>`;

  API.get('/api/v1/agents/overview').then((o) => {
    document.getElementById('agent-kpi').innerHTML =
      U.kpi('Agent 会话', U.int(o.session_total), `拒识 ${U.int(o.rejected_count)} 次`, true)
      + U.kpi('拒识率', U.pct(o.reject_rate), '低置信度转人工')
      + U.kpi('待终审', U.int(o.pending_review), `已判定 ${U.int(o.decided_review)}`)
      + U.kpi('平均探查区域', U.num(o.avg_probed_regions, 1), '对标业内 47 个区域');
  }).catch((e) => { document.getElementById('agent-kpi').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });

  API.get('/api/v1/agents/architecture').then((a) => {
    document.getElementById('agent-arch').innerHTML = (a.agents || []).map((ag) =>
      `<div style="padding:8px 0;border-bottom:1px dashed var(--line)">
        <strong>${U.esc(ag.name)}</strong> <span class="mono" style="color:#667a8c">${U.esc(ag.key)}</span>
        <div class="muted">${U.esc(ag.responsibility || ag.description || '')}</div></div>`).join('');
  }).catch(() => {});

  API.get('/api/v1/slides?page_size=200').then((d) => {
    const sel = document.getElementById('agent-slide');
    sel.innerHTML = (d.items || []).map((s) => `<option value="${s.id}">${U.esc(s.code)} · ${U.esc(s.case_no)} · ${s.has_lesion ? '阳性' : '阴性'}</option>`).join('');
  }).catch(() => {});
  document.getElementById('agent-run').onclick = async (e) => {
    const btn = e.target; btn.disabled = true;
    const sid = document.getElementById('agent-slide').value;
    document.getElementById('agent-run-hint').innerHTML = '<span class="pulse"></span> 正在执行多轮探查与证据整合…（约 10—40 秒）';
    try {
      const r = await API.post('/api/v1/agents/run', { slide_id: Number(sid) });
      document.getElementById('agent-run-hint').innerHTML =
        `完成：${U.esc(r.verdict || '—')}（探查 ${U.int(r.probed_region_count)} 区域、证据 ${U.int(r.evidence_count)} 条`
        + `${r.rejected ? '，已拒识转人工' : ''}）`;
      U.toast('Agent 分析完成', 'ok');
      document.getElementById('agent-list').querySelector('.panel').reload();
      openAgentSession(r.id);
    } catch (err) {
      document.getElementById('agent-run-hint').textContent = '运行失败：' + err.message;
      U.toast(err.message, 'err');
    } finally { btn.disabled = false; }
  };

  document.getElementById('agent-list').appendChild(listPanel({
    endpoint: '/api/v1/agents/sessions',
    columns: [
      { key: 'code', label: '会话编号' },
      { key: 'slide_code', label: '切片' },
      { key: 'task_code', label: '任务' },
      { key: 'verdict', label: '结论', render: (r) => U.tag(r.verdict || '—', r.verdict === '阳性' ? 'danger' : (r.verdict === '拒识' ? 'warn' : 'ok')) },
      { key: 'confidence_level', label: '置信度' },
      { key: 'probed_region_count', label: '探查区域', align: 'right' },
      { key: 'evidence_count', label: '证据条数', align: 'right' },
      { key: 'rejected', label: '拒识', render: (r) => (r.rejected ? U.tag('拒识', 'warn') : '—') },
      { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
    ],
    onRow: (row) => openAgentSession(row.id),
  }));
}

async function openAgentSession(sessionId) {
  U.modal('Agent 会话详情', U.loading('加载可追溯链'));
  try {
    const d = await API.get(`/api/v1/agents/sessions/${sessionId}/detail`);
    const steps = (d.steps || []).map((s) => `<div class="step"><span class="agent">${U.tag(s.agent)}</span>
      <span class="act">${U.esc(s.action)}</span><span class="out">${U.esc(s.output_summary || '')}</span></div>`).join('');
    const evidence = (d.evidence || []).map((e) => `<div class="evidence">
      <div class="claim">${U.esc(e.claim)}</div>
      <div class="meta">${U.esc(e.evidence_type)} · 来源：${U.esc(e.source_desc || '—')} · 强度：${U.esc(e.strength || '—')} ·
        置信：${U.num(e.score, 3)} · 智能体：${U.esc(e.agent)}</div></div>`).join('');
    const diagnoses = (d.diagnoses || []).map((x) => `<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px dashed var(--line)">
      <span>${U.esc(x.diagnosis_name)}</span><span class="mono">${U.num(x.probability, 4)}</span></div>`).join('');
    U.modal(`Agent 会话 ${d.code} · ${d.verdict || ''}`, `
      <div class="grid c4" style="margin-bottom:14px">
        ${U.kpi('结论', d.verdict || '—')}${U.kpi('置信度', (d.confidence_level || '—').toUpperCase())}
        ${U.kpi('探查区域', U.int(d.probed_region_count))}${U.kpi('证据条数', U.int(d.evidence_count))}
      </div>
      ${d.rejected ? `<div class="note" style="border-left-color:#e08a00;background:#fdf7ec;border-color:#f4dcae;margin-bottom:12px">触发拒识：${U.esc(d.reject_reason || '低置信度，转人工复核')}</div>` : ''}
      <h4>智能体轨迹</h4>${steps || U.empty('无轨迹')}
      <h4 style="margin-top:14px">证据链（每条结论 → 证据 → 来源）</h4>${evidence || U.empty('无证据')}
      ${diagnoses ? `<h4 style="margin-top:14px">鉴别诊断排序</h4>${diagnoses}` : ''}
      ${d.summary_text ? `<h4 style="margin-top:14px">结构化报告</h4><div class="note">${U.esc(d.summary_text).replace(/\n/g, '<br>')}</div>` : ''}`);
  } catch (e) { U.modal('加载失败', U.esc(e.message)); }
}

/* =============================================================== 07 评测基座 */
function renderEvaluation(root) {
  root.innerHTML = `
    <div class="grid c4" id="eval-kpi" style="margin-bottom:16px"></div>
    <div id="eval-list"></div>`;
  API.get('/api/v1/eval/overview').then((o) => {
    document.getElementById('eval-kpi').innerHTML =
      U.kpi('评测集', U.int(o.dataset_count), `外部验证集 ${U.int(o.external_dataset_count)}`, true)
      + U.kpi('评测运行', U.int(o.run_count), '含跨中心与 MRMC')
      + U.kpi('数据集类型', U.int(Object.keys(o.datasets_by_kind || {}).length), Object.keys(o.datasets_by_kind || {}).join(' / '))
      + U.kpi('最近运行', (o.recent_runs || [])[0] ? U.num((o.recent_runs[0] || {}).auroc, 4) : '—', '最近一次 AUROC');
  }).catch((e) => { document.getElementById('eval-kpi').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });

  document.getElementById('eval-list').appendChild(listPanel({
    endpoint: '/api/v1/eval/runs',
    columns: [
      { key: 'code', label: '运行编号' },
      { key: 'model_version_label', label: '模型版本' },
      { key: 'task_code', label: '任务' },
      { key: 'auroc', label: 'AUROC', align: 'right', render: (r) => U.num(r.auroc, 4) },
      { key: 'sensitivity', label: '敏感度', align: 'right', render: (r) => U.num(r.sensitivity, 3) },
      { key: 'specificity', label: '特异度', align: 'right', render: (r) => U.num(r.specificity, 3) },
      { key: 'ece', label: 'ECE', align: 'right', render: (r) => U.num(r.ece, 4) },
      { key: 'threshold', label: '阈值', align: 'right', render: (r) => U.num(r.threshold, 2) },
      { key: 'created_at', label: '时间', render: (r) => U.date(r.created_at) },
    ],
    onRow: (row) => openEvalRun(row.id),
  }));
}

async function openEvalRun(runId) {
  U.modal('评测运行详情', U.loading('加载 ROC / 混淆矩阵 / 分组指标'));
  try {
    const d = await API.get(`/api/v1/eval/runs/${runId}/detail`);
    const roc = (d.roc_points || d.roc || d.roc_curve || []).map((p) => ({ x: p.fpr !== undefined ? p.fpr : p.x, y: p.tpr !== undefined ? p.tpr : p.y }));
    const groups = d.by_group || d.by_site || {};
    const groupHtml = Object.entries(groups).map(([k, v]) => {
      const auroc = typeof v === 'object' ? v.auroc : v;
      return `<div class="bar-row"><span class="name">${U.esc(k)}</span><span class="bar-track"><span class="bar-fill" style="width:${(Number(auroc) * 100).toFixed(1)}%"></span></span><span class="val">${U.num(auroc, 4)}</span></div>`;
    }).join('');
    const cm = d.confusion || d.confusion_matrix;
    U.modal(`评测运行 ${d.code}`, `
      <div class="grid c4" style="margin-bottom:14px">
        ${U.kpi('AUROC', U.num(d.auroc, 4), d.auroc_ci_low ? `95%CI ${U.num(d.auroc_ci_low, 4)}–${U.num(d.auroc_ci_high, 4)}` : '')}
        ${U.kpi('敏感度', U.num(d.sensitivity, 3))}${U.kpi('特异度', U.num(d.specificity, 3))}
        ${U.kpi('ECE', U.num(d.ece, 4), '校准误差')}
      </div>
      <div class="grid c2">
        <div class="card tight"><h4>ROC 曲线</h4>${U.lineChart(roc, { diagonal: true, xLabel: '假阳性率 FPR', yLabel: '真阳性率 TPR' })}</div>
        <div class="card tight"><h4>按中心分组 AUROC（跨中心泛化衰减）</h4>${groupHtml || U.empty('无分组数据')}
          <div class="note" style="margin-top:10px">院内与院外的差距就是「泛化衰减」；它是 R3 风险的量化证据，也是补数据的依据。</div>
        </div>
      </div>
      ${cm ? `<h4 style="margin-top:14px">混淆矩阵</h4><pre class="mono">${U.esc(JSON.stringify(cm, null, 2))}</pre>` : ''}
      ${(d.metrics || []).length ? `<h4 style="margin-top:14px">指标明细</h4>${U.table([
        { key: 'metric_key', label: '指标' }, { key: 'metric_value', label: '取值', align: 'right', render: (r) => U.num(r.metric_value, 4) },
        { key: 'group_key', label: '分组' }, { key: 'note', label: '说明' },
      ], d.metrics)}` : ''}`);
  } catch (e) { U.modal('加载失败', U.esc(e.message)); }
}

/* =============================================================== 08 合规与注册 */
function renderCompliance(root) {
  root.innerHTML = `
    <div class="grid c3" style="margin-bottom:16px">
      <div class="card"><h4>注册就绪度</h4><div id="c-ready"></div></div>
      <div class="card"><h4>审计链完整性</h4><div id="c-audit"></div></div>
      <div class="card"><h4>可解释性四件套</h4><div id="c-explain"></div></div>
    </div>
    <div id="c-list"></div>`;
  API.get('/api/v1/compliance/overview').then((o) => {
    const r = o.readiness || {};
    document.getElementById('c-ready').innerHTML = `
      <div class="kpi"><span class="value">${U.pct(r.readiness_score)}</span>
      <span class="foot">${U.int(r.passed_count)}/${U.int(r.total_count)} 项通过</span></div>
      ${(r.items || []).map((i) => `<div style="display:flex;justify-content:space-between;padding:5px 0;font-size:12.5px">
        <span>${U.esc(i.label || i.key)}</span>${i.passed ? U.tag('通过', 'ok') : U.tag('待办', 'warn')}</div>`).join('')}
      ${(r.blocked_review_labels || []).length ? `<div class="chips" style="margin-top:8px">${r.blocked_review_labels.map((s) => `<span class="chip danger">${U.esc(s)}</span>`).join('')}</div>` : ''}`;
    const c = o.audit_chain || {};
    document.getElementById('c-audit').innerHTML = `
      <div class="kpi"><span class="value">${U.int(c.total)}</span><span class="foot">条记录 · 完整 ${U.int(c.verified || c.intact)}</span></div>
      <div class="muted" style="margin-top:6px">算法：${U.esc(c.algorithm || 'SHA256 哈希链')}</div>
      <div style="margin-top:8px">${c.broken ? U.tag('存在断裂', 'danger') : U.tag('校验通过', 'ok')}</div>`;
  }).catch((e) => { document.getElementById('c-ready').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });
  API.get('/api/v1/compliance/explainability').then((o) => {
    document.getElementById('c-explain').innerHTML = (o.framework || []).map((f) => `
      <div style="padding:6px 0;border-bottom:1px dashed var(--line)"><strong>${U.esc(f.label)}</strong>
      <div class="muted">${U.esc(f.question)}</div></div>`).join('');
  }).catch(() => {});
  document.getElementById('c-list').appendChild(listPanel({
    endpoint: '/api/v1/compliance/review-answers',
    columns: [
      { key: 'group_label', label: '关口' },
      { key: 'code', label: '编码' },
      { key: 'question', label: '审评问题' },
      { key: 'answer', label: '应答要点' },
      { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
      { key: 'owner_name', label: '责任人' },
    ],
    emptyText: '暂无应答台账',
  }));
}

/* =============================================================== 09 云边协同 */
function renderEdge(root) {
  root.innerHTML = `
    <div class="grid c5" id="edge-kpi" style="margin-bottom:16px"></div>
    <div id="edge-fed" class="grid c2" style="margin-bottom:16px"></div>
    <div id="edge-list"></div>`;
  API.get('/api/v1/edge/overview').then((o) => {
    document.getElementById('edge-kpi').innerHTML =
      U.kpi('边缘节点', `${U.int(o.online_count)}/${U.int(o.node_total)}`, `在线/总数`, true)
      + U.kpi('支持实时推理', U.int(o.realtime_capable), 'PC 端轻量版本')
      + U.kpi('本地切片', U.int(o.local_slide_total), '数据不出域')
      + U.kpi('平均时延', `${U.num(o.avg_latency_ms, 0)} ms`, '')
      + U.kpi('最短部署', o.min_deploy_minutes !== null ? `${U.int(o.min_deploy_minutes)} 分钟` : '—', '分钟级部署');
  }).catch((e) => { document.getElementById('edge-kpi').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });
  API.get('/api/v1/edge/federated-jobs?page_size=1').then((d) => {
    const job = (d.items || [])[0];
    if (!job) { document.getElementById('edge-fed').innerHTML = '<div class="empty">暂无联邦任务</div>'; return; }
    API.get(`/api/v1/edge/federated-jobs/${job.id}/detail`).then((f) => {
      document.getElementById('edge-fed').innerHTML = `
        <div class="card"><h4>联邦式增量微调 · ${U.esc(f.code)}</h4>
          <div class="grid c3" style="margin-bottom:10px">
            ${U.kpi('初始 → 最终', `${U.num(f.global_metric_init, 4)} → ${U.num(f.global_metric_final, 4)}`)}
            ${U.kpi('轮次', U.int(f.current_round))}
            ${U.kpi('样本出域', U.int(f.sample_left_domain_count), '必须恒为 0')}
          </div>
          ${U.lineChart((f.metric_series || []).map((m) => ({ x: m.round, y: m.metric })), { xLabel: '轮次', yLabel: '全局 AUROC', height: 240 })}
        </div>
        <div class="card"><h4>逐轮参与方（数据不出域证据）</h4>
          ${U.table([
            { key: 'round_no', label: '轮次', align: 'right' },
            { key: 'client_count', label: '参与方', align: 'right' },
            { key: 'global_metric', label: '全局指标', align: 'right', render: (r) => U.num(r.global_metric, 4) },
            { key: 'upload_kb', label: '上传 KB', align: 'right' },
            { key: 'aggregated_at', label: '聚合时间' },
          ], f.rounds || [])}
          <div class="note" style="margin-top:10px">只交换模型参数（约 1 MB 量级），数万张切片原始影像始终留在各机构本地。</div>
        </div>`;
    });
  }).catch(() => {});
  document.getElementById('edge-list').appendChild(listPanel({
    endpoint: '/api/v1/edge/nodes',
    columns: [
      { key: 'code', label: '节点' }, { key: 'name', label: '名称' }, { key: 'hospital', label: '机构' },
      { key: 'node_type', label: '形态' }, { key: 'deployment_mode', label: '部署模式' },
      { key: 'gpu_count', label: 'GPU', align: 'right' }, { key: 'local_slide_count', label: '本地切片', align: 'right' },
      { key: 'realtime_inference', label: '实时推理', render: (r) => (r.realtime_inference ? U.tag('支持', 'ok') : '—') },
      { key: 'latency_ms', label: '时延(ms)', align: 'right' },
      { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
    ],
    filters: [{ key: 'status', label: '状态', type: 'select', options: ['online', 'offline', 'degraded', 'maintenance'] }],
  }));
}

/* =============================================================== 10 注册与路线图 */
function renderRegistry(root) {
  root.innerHTML = `
    <div class="card" style="margin-bottom:16px"><h4>注册时间轴（P0—P3 · 30 个月）</h4><div id="reg-gantt"></div></div>
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card"><h4>风险 2×2 矩阵</h4><div id="reg-risk"></div></div>
      <div class="card"><h4>前置风险清单（P0 必须有动作）</h4><div id="reg-front"></div></div>
    </div>
    <div id="reg-list"></div>`;
  API.get('/api/v1/registry/timeline').then((d) => {
    const months = d.total_months || 30;
    const rows = (d.milestones || []).map((m) => {
      const left = (m.target_month / months) * 100;
      return `<div class="gantt-row"><span class="lbl">${U.esc(m.code)} ${U.esc(m.title)}</span>
        <span class="gantt-track"><span class="gantt-bar ${String(m.phase).toLowerCase()}" style="left:${Math.max(0, left - 8).toFixed(1)}%;width:8%"></span></span>
        <span class="val" style="width:64px;text-align:right;font-size:11.5px;color:#667a8c">${U.esc(m.status)}</span></div>`;
    }).join('');
    const stages = (d.stages || []).map((s) => {
      const left = (s.start_month / months) * 100, width = ((s.end_month - s.start_month) / months) * 100;
      return `<div class="gantt-row"><span class="lbl">${U.esc(s.name)}</span>
        <span class="gantt-track"><span class="gantt-bar" style="left:${left.toFixed(1)}%;width:${width.toFixed(1)}%"></span></span>
        <span style="width:64px;text-align:right;font-size:11.5px;color:#667a8c">${s.start_month}–${s.end_month} 月</span></div>`;
    }).join('');
    document.getElementById('reg-gantt').innerHTML = `<div class="gantt">${stages}<div style="height:8px"></div>${rows}</div>
      <div class="gantt-axis">${[0, 0.25, 0.5, 0.75, 1].map((p) => `<span>第 ${Math.round(months * p)} 月</span>`).join('')}</div>`;
  }).catch((e) => { document.getElementById('reg-gantt').innerHTML = `<div class="empty">${U.esc(e.message)}</div>`; });
  API.get('/api/v1/registry/risks/board').then((b) => {
    const q = b.quadrants || {};
    const names = { critical: '高概率·高影响', watch: '低概率·高影响', monitor: '高概率·低影响', low: '低概率·低影响', high_high: '高概率·高影响', high_low: '高概率·低影响', low_high: '低概率·高影响', low_low: '低概率·低影响' };
    const cell = (title, list) => `<div class="cell"><div class="t">${U.esc(title)}（${(list || []).length}）</div>
      ${(list || []).map((r) => `<div style="font-size:11.5px">${U.esc(r.code)} ${U.esc(r.title)}</div>`).join('') || '<span class="muted">—</span>'}</div>`;
    document.getElementById('reg-risk').innerHTML = `<div class="matrix">
      <div class="axis">高影响</div>${cell('高概率', q.critical || q.high_high)}${cell('低概率', q.watch || q.low_high)}
      <div class="axis">低影响</div>${cell('高概率', q.monitor || q.high_low)}${cell('低影响', q.monitor || q.low_low)}</div>`;
    document.getElementById('reg-front').innerHTML = (b.frontloaded || []).map((r) => `
      <div style="padding:8px 0;border-bottom:1px dashed var(--line)">
        <div style="display:flex;justify-content:space-between"><strong>${U.esc(r.code)} ${U.esc(r.title)}</strong>
        <span>${U.tag('风险分 ' + r.risk_score, r.risk_score >= 15 ? 'danger' : (r.risk_score >= 9 ? 'warn' : ''))}</span></div>
        <div class="muted">P0 动作：${U.esc(r.p0_action || '待补充')}</div>
        ${r.budget_note ? `<div class="muted">预算：${U.esc(r.budget_note)}</div>` : ''}</div>`).join('') || U.empty();
  }).catch(() => {});
  document.getElementById('reg-list').appendChild(listPanel({
    endpoint: '/api/v1/registry/risks',
    columns: [
      { key: 'code', label: '编号' }, { key: 'title', label: '风险' },
      { key: 'layer', label: '类别' },
      { key: 'likelihood', label: '概率', align: 'right' }, { key: 'severity', label: '影响', align: 'right' },
      { key: 'risk_score', label: '分值', align: 'right', render: (r) => U.tag(r.risk_score, r.risk_score >= 15 ? 'danger' : (r.risk_score >= 9 ? 'warn' : '')) },
      { key: 'is_frontloaded', label: '前置', render: (r) => (r.is_frontloaded ? U.tag('前置', 'danger') : '—') },
      { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
      { key: 'owner_name', label: '责任人' },
    ],
    filters: [{ key: 'layer', label: '类别', type: 'select', options: ['data', 'technical', 'clinical', 'commercial', 'compliance', 'team'] },
              { key: 'status', label: '状态' }],
  }));
}

/* =============================================================== 11 运营看板 */
function renderOps(root) {
  root.innerHTML = `
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card"><h4>团队编制（按职能簇）</h4><div id="ops-team"></div></div>
      <div class="card"><h4>成本结构（相对比例）</h4><div id="ops-cost"></div></div>
    </div>
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card"><h4>收入路径（分阶段）</h4><div id="ops-rev"></div></div>
      <div class="card"><h4>立项决策事项</h4><div id="ops-dec"></div></div>
    </div>
    <div id="ops-list"></div>`;
  API.get('/api/v1/ops/team-plan').then((o) => {
    document.getElementById('ops-team').innerHTML =
      `<div class="muted" style="margin-bottom:8px">建议 ${U.int(o.total_suggested)} 人（区间 ${U.int(o.total_min)}—${U.int(o.total_max)} 人）</div>`
      + U.bars(Object.entries(o.by_cluster || {}).map(([k, v]) => ({ name: (o.cluster_labels || {})[k] || k, value: v.suggested, display: v.suggested + ' 人' })))
      + `<div class="note" style="margin-top:8px">P0 必需岗：${U.esc((o.mandatory_in_p0 || []).join('、') || '—')}</div>`;
  }).catch(() => {});
  API.get('/api/v1/ops/cost-structure').then((o) => {
    document.getElementById('ops-cost').innerHTML = U.bars((o.items || []).map((i) => ({ name: i.category, value: i.ratio_high, display: U.pct(i.ratio_high) })))
      + `<div class="note" style="margin-top:8px">${U.esc(o.elasticity_note || '')}</div>`;
  }).catch(() => {});
  API.get('/api/v1/ops/revenue-plan').then((o) => {
    document.getElementById('ops-rev').innerHTML = U.table([
      { key: 'name', label: '路径' }, { key: 'phase', label: '阶段', render: (r) => U.tag(r.phase, 'sky') },
      { key: 'path_type', label: '类型' }, { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
    ], o.items || []) + `<div class="note" style="margin-top:8px">${U.esc(o.note || '')}</div>`;
  }).catch(() => {});
  API.get('/api/v1/ops/decision-board').then((o) => {
    document.getElementById('ops-dec').innerHTML = (o.items || []).map((x) => `
      <div style="padding:8px 0;border-bottom:1px dashed var(--line)">
        <div style="display:flex;justify-content:space-between"><strong>${U.esc(x.title)}</strong>${U.statusTag(x.status)}</div>
        <div class="muted">${U.esc(x.content || '')}</div></div>`).join('') + `<div class="note" style="margin-top:8px">${U.esc(o.note || '')}</div>`;
  }).catch(() => {});
  document.getElementById('ops-list').appendChild(listPanel({
    endpoint: '/api/v1/ops/kpi-snapshots',
    columns: [
      { key: 'snapshot_date', label: '快照日期' },
      { key: 'slide_count', label: '切片', align: 'right' },
      { key: 'annotated_slide_count', label: '已标注', align: 'right' },
      { key: 'feature_ready_count', label: '特征就绪', align: 'right' },
      { key: 'model_auroc', label: '院内 AUROC', align: 'right', render: (r) => U.num(r.model_auroc, 4) },
      { key: 'external_auroc', label: '外部 AUROC', align: 'right', render: (r) => U.num(r.external_auroc, 4) },
      { key: 'agent_reject_rate', label: '拒识率', align: 'right', render: (r) => U.pct(r.agent_reject_rate) },
      { key: 'milestone_done', label: '里程碑', align: 'right', render: (r) => `${r.milestone_done}/${r.milestone_total}` },
    ],
  }));
}

/* =============================================================== 12 系统管理 */
function renderSystem(root) {
  root.innerHTML = '<div id="sys-list"></div>';
  document.getElementById('sys-list').appendChild(listPanel({
    endpoint: '/api/v1/system/users',
    columns: [
      { key: 'username', label: '账号' }, { key: 'real_name', label: '姓名' },
      { key: 'department', label: '科室/部门' }, { key: 'title', label: '职务' },
      { key: 'roles', label: '角色', render: (r) => (r.roles || r.role_names || []).map((x) => U.tag(x, 'sky')).join(' ') },
      { key: 'deployment_env', label: '环境', render: (r) => U.tag(r.deployment_env, r.deployment_env === 'product' ? 'danger' : '') },
      { key: 'is_active', label: '启用', render: (r) => (r.is_active ? U.tag('启用', 'ok') : U.tag('停用', 'danger')) },
      { key: 'last_login_at', label: '最近登录', render: (r) => U.date(r.last_login_at) },
    ],
    searchable: true,
  }));
}

/* =============================================================== 模块表 */
const MODULES = [
  { key: 'overview', idx: '00', label: '总览', render: renderOverview },
  { key: 'jobs', idx: '01', label: '任务中心', render: renderJobs },
  { key: 'ingest', idx: '02', label: '数据接入', render: renderIngest },
  { key: 'workbench', idx: '03', label: '标注工作台', render: renderWorkbench },
  { key: 'assets', idx: '04', label: '数据资产', render: renderAssets },
  { key: 'labels', idx: '05', label: '标签体系', render: renderLabels },
  { key: 'models', idx: '06', label: '模型与算力', render: renderModels },
  { key: 'pipeline', idx: '07', label: '推理流水线', render: renderPipeline },
  { key: 'agents', idx: '08', label: '智慧医疗 Agent', render: renderAgents },
  { key: 'evaluation', idx: '09', label: '评测基座', render: renderEvaluation },
  { key: 'compliance', idx: '10', label: '合规与注册', render: renderCompliance },
  { key: 'edge', idx: '11', label: '云边协同', render: renderEdge },
  { key: 'registry', idx: '12', label: '注册与路线图', render: renderRegistry },
  { key: 'ops', idx: '13', label: '运营看板', render: renderOps },
  { key: 'system', idx: '14', label: '系统管理', render: renderSystem },
];


/* =============================================================== 通用表单弹窗
 * 商用系统与演示系统最直观的差别：演示系统只有只读看板，真实系统必须能写。
 * 这里提供一个按字段描述渲染的表单引擎，供各模块的「新建 / 编辑」复用。
 */
function formModal(cfg) {
  const fields = cfg.fields || [];
  const values = Object.assign({}, cfg.values || {});
  const body = fields.map((f) => {
    const v = values[f.key] === undefined || values[f.key] === null ? '' : values[f.key];
    let control;
    if (f.type === 'select') {
      const opts = (f.options || []).map((o) => {
        const val = typeof o === 'string' ? o : o.value;
        const lab = typeof o === 'string' ? o : o.label;
        return `<option value="${U.esc(val)}" ${String(v) === String(val) ? 'selected' : ''}>${U.esc(lab)}</option>`;
      }).join('');
      control = `<select data-k="${U.esc(f.key)}"><option value="">—</option>${opts}</select>`;
    } else if (f.type === 'textarea') {
      control = `<textarea data-k="${U.esc(f.key)}" rows="${f.rows || 3}">${U.esc(v)}</textarea>`;
    } else if (f.type === 'checkbox') {
      control = `<input type="checkbox" data-k="${U.esc(f.key)}" ${v === true || v === 'true' ? 'checked' : ''} />`;
    } else {
      control = `<input type="${f.type || 'text'}" data-k="${U.esc(f.key)}" value="${U.esc(v)}"
                   ${f.placeholder ? `placeholder="${U.esc(f.placeholder)}"` : ''} />`;
    }
    return `<label style="display:block;margin-bottom:12px">
      <span style="font-size:12.5px;color:#34495a">${U.esc(f.label)}${f.required ? ' <span style="color:#d64545">*</span>' : ''}</span>
      <div style="margin-top:4px">${control}</div>
      ${f.hint ? `<div style="font-size:11.5px;color:#9fb0bd;margin-top:3px">${U.esc(f.hint)}</div>` : ''}
    </label>`;
  }).join('');

  U.modal(cfg.title || '表单', `
    <form id="dyn-form">${body}
      <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:6px">
        <button type="button" class="btn ghost" id="dyn-cancel">取消</button>
        <button type="submit" class="btn" id="dyn-submit">${U.esc(cfg.submitText || '保存')}</button>
      </div>
      <div id="dyn-error" style="color:#d64545;font-size:12.5px;margin-top:8px"></div>
    </form>`);

  document.getElementById('dyn-cancel').onclick = U.closeModal;
  document.getElementById('dyn-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('dyn-submit');
    const errEl = document.getElementById('dyn-error');
    const payload = {};
    document.querySelectorAll('#dyn-form [data-k]').forEach((node) => {
      const key = node.getAttribute('data-k');
      const field = fields.find((f) => f.key === key) || {};
      if (field.readonly) return;
      if (node.type === 'checkbox') payload[key] = node.checked;
      else if (field.type === 'number') payload[key] = node.value === '' ? null : Number(node.value);
      else payload[key] = node.value.trim();
    });
    const missing = fields.filter((f) => f.required && (payload[f.key] === '' || payload[f.key] === undefined
      || payload[f.key] === null));
    if (missing.length) { errEl.textContent = '必填项未填写：' + missing.map((f) => f.label).join('、'); return; }

    btn.disabled = true; btn.textContent = '提交中…'; errEl.textContent = '';
    try {
      await cfg.onSubmit(payload);
      U.closeModal();
      U.toast(cfg.successText || '已保存', 'ok');
      if (cfg.after) cfg.after();
    } catch (err) {
      errEl.textContent = err.message + (err.traceId ? `（trace ${err.traceId}）` : '');
    } finally {
      btn.disabled = false; btn.textContent = cfg.submitText || '保存';
    }
  });
}

/* =============================================================== 13 数据接入 */
function renderIngest(root) {
  root.innerHTML = `
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card">
        <h4>上传切片文件</h4>
        <p class="muted" style="margin:4px 0 12px">
          支持 svs / tif / ndpi / mrxs / scn / png / jpg / npz，单文件上限 4 GB。
          采用流式落盘并按 SHA256 去重，重复文件会被直接拒绝而不是静默入库两次。
        </p>
        <form id="up-form">
          <div class="grid c2">
            <label>切片编号<input type="text" name="code" placeholder="留空则用文件名" /></label>
            <label>病例号<input type="text" name="case_no" /></label>
            <label>器官<input type="text" name="organ" placeholder="淋巴结" /></label>
            <label>病种<input type="text" name="cancer_type" placeholder="淋巴结转移" /></label>
            <label>染色<input type="text" name="staining" value="H&E" /></label>
            <label>中心编号<input type="text" name="site_code" placeholder="SITE-A" /></label>
            <label>物理分辨率 mpp<input type="number" step="0.01" name="mpp" value="0.5" /></label>
            <label>标签
              <select name="has_lesion"><option value="false">阴性</option><option value="true">阳性</option></select>
            </label>
          </div>
          <div style="margin-top:10px">
            <input type="file" id="up-file" />
            <label style="display:inline-block;margin-left:12px;font-size:12.5px">
              <input type="checkbox" id="up-precompute" checked /> 上传后自动排队特征预计算
            </label>
          </div>
          <div style="margin-top:12px;display:flex;gap:10px;align-items:center">
            <button type="submit" class="btn sky" id="up-btn">上传并登记</button>
            <button type="button" class="btn ghost" id="up-batch">批量上传（多选）</button>
            <span id="up-progress" class="muted"></span>
          </div>
        </form>
        <div id="up-result" style="margin-top:12px"></div>
      </div>

      <div class="card">
        <h4>按 CSV 批量导入元数据</h4>
        <p class="muted" style="margin:4px 0 12px">
          先体检再入库：上传后立刻告诉你「第几行、哪一列、错在哪」，避免改表重传来回三轮。
        </p>
        <div class="toolbar">
          <a class="btn ghost" href="/api/v1/uploads/template.csv" target="_blank">下载导入模板</a>
        </div>
        <input type="file" id="csv-file" accept=".csv" />
        <div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn ghost" id="csv-validate">仅体检</button>
          <button class="btn" id="csv-import">体检并导入</button>
        </div>
        <div id="csv-result" style="margin-top:12px"></div>
      </div>
    </div>
    <div class="card"><h4>最近上传与导入</h4><div id="ingest-recent">${U.loading('')}</div></div>`;

  const form = document.getElementById('up-form');
  const progressEl = document.getElementById('up-progress');

  function buildFormData(file, extra) {
    const fd = new FormData();
    fd.append('file', file);
    const data = extra || {};
    ['code', 'case_no', 'organ', 'cancer_type', 'staining', 'site_code', 'mpp'].forEach((k) => {
      if (data[k] !== undefined && data[k] !== '') fd.append(k, data[k]);
    });
    fd.append('has_lesion', data.has_lesion || 'false');
    fd.append('auto_precompute', document.getElementById('up-precompute').checked ? 'true' : 'false');
    return fd;
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const file = document.getElementById('up-file').files[0];
    if (!file) { U.toast('请先选择文件', 'err'); return; }
    const btn = document.getElementById('up-btn');
    btn.disabled = true;
    const extra = {};
    new FormData(form).forEach((v, k) => { extra[k] = v; });
    try {
      const data = await API.upload('/api/v1/uploads/slides', buildFormData(file, extra),
        (p) => { progressEl.textContent = `上传中 ${(p * 100).toFixed(0)}%`; });
      progressEl.textContent = '';
      document.getElementById('up-result').innerHTML = `
        <div class="note">已登记切片 <strong>${U.esc(data.slide.code)}</strong>
        （${data.file_mb} MB，SHA256 ${U.esc(data.checksum.slice(0, 12))}…）
        ${data.auto_precompute_job ? `，特征预计算作业 ${U.esc(data.auto_precompute_job.code)} 已排队` : ''}</div>`;
      U.toast('上传成功', 'ok');
      form.reset();
      loadRecent();
    } catch (err) {
      progressEl.textContent = '';
      document.getElementById('up-result').innerHTML = `<div class="empty">${U.esc(err.message)}</div>`;
      U.toast(err.message, 'err');
    } finally { btn.disabled = false; }
  });

  document.getElementById('up-batch').onclick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async () => {
      if (!input.files.length) return;
      const fd = new FormData();
      Array.from(input.files).forEach((f) => fd.append('files', f));
      fd.append('default_site_code', form.elements.site_code.value || '');
      fd.append('auto_precompute', document.getElementById('up-precompute').checked ? 'true' : 'false');
      try {
        const data = await API.upload('/api/v1/uploads/slides/batch', fd,
          (p) => { progressEl.textContent = `批量上传 ${(p * 100).toFixed(0)}%`; });
        progressEl.textContent = '';
        document.getElementById('up-result').innerHTML = `
          <div class="note">成功 ${data.accepted_count} / 失败 ${data.rejected_count}</div>
          ${data.rejected.length ? U.table([
            { key: 'filename', label: '文件' }, { key: 'error', label: '失败原因' }], data.rejected) : ''}`;
        loadRecent();
      } catch (err) { progressEl.textContent = ''; U.toast(err.message, 'err'); }
    };
    input.click();
  };

  document.getElementById('csv-validate').onclick = async () => {
    const file = document.getElementById('csv-file').files[0];
    if (!file) { U.toast('请先选择 CSV', 'err'); return; }
    const fd = new FormData(); fd.append('file', file);
    try {
      const d = await API.upload('/api/v1/uploads/validate-csv', fd);
      document.getElementById('csv-result').innerHTML = `
        <div class="note">共 ${d.row_count} 行、${d.column_count} 列 · <strong>${U.esc(d.verdict)}</strong></div>
        ${d.missing_required_columns.length ? `<div class="empty">缺少必填列：${d.missing_required_columns.join('、')}</div>` : ''}
        ${d.problem_count ? U.table([
          { key: 'row', label: '行号', width: '70px' }, { key: 'field', label: '字段', width: '120px' },
          { key: 'error', label: '问题' }], d.problems) : ''}`;
    } catch (err) { U.toast(err.message, 'err'); }
  };

  document.getElementById('csv-import').onclick = async () => {
    const file = document.getElementById('csv-file').files[0];
    if (!file) { U.toast('请先选择 CSV', 'err'); return; }
    const fd = new FormData();
    fd.append('file', file);
    fd.append('site_code', form.elements.site_code.value || '');
    fd.append('split', 'train');
    fd.append('enqueue_precompute', 'true');
    try {
      const d = await API.upload('/api/v1/uploads/slides/csv', fd);
      document.getElementById('csv-result').innerHTML = `
        <div class="note">已解析 ${d.row_count} 行。导入作业 <strong>${U.esc(d.job.code)}</strong> 已提交，
        可在<a href="#/jobs">任务中心</a>查看进度。</div>`;
      U.toast('导入作业已提交', 'ok');
    } catch (err) { U.toast(err.message, 'err'); }
  };

  async function loadRecent() {
    try {
      const d = await API.get('/api/v1/jobs?job_type=import_slides&page_size=5');
      const j = await API.get('/api/v1/jobs?job_type=feature_precompute&page_size=5');
      document.getElementById('ingest-recent').innerHTML =
        U.table([
          { key: 'code', label: '作业' }, { key: 'type_label', label: '类型' },
          { key: 'title', label: '说明' },
          { key: 'status', label: '状态', render: (r) => U.statusTag(r.status) },
          { key: 'progress', label: '进度', align: 'right', render: (r) => U.pct(r.progress) },
        ], (d.items || []).concat(j.items || []), { emptyText: '暂无导入或预计算作业' });
    } catch (err) {
      document.getElementById('ingest-recent').innerHTML = `<div class="empty">${U.esc(err.message)}</div>`;
    }
  }
  loadRecent();
}

/* =============================================================== 14 任务中心 */
function renderJobs(root) {
  window.__shTimers = window.__shTimers || [];
  // 上一个视图的事件流必须关掉：切走后还挂着 a 连接，浏览器对同源
  // EventSource 有连接数上限（通常 6），多切几次就再也连不上了。
  if (window.__shEventStream) {
    try { window.__shEventStream.close(); } catch (_) {}
    window.__shEventStream = null;
  }
  root.innerHTML = `
    <div id="job-todo" style="margin-bottom:16px">${U.loading('汇总待办')}</div>
    <div class="grid c4" id="job-kpi" style="margin-bottom:16px"></div>
    <div class="card" style="margin-bottom:16px">
      <h4>作业列表
        <span class="sub" id="job-stream-state">正在建立实时通道…</span>
      </h4>
      <div id="job-list">${U.loading('')}</div>
    </div>`;

  async function loadTodo() {
    try {
      const w = await API.get('/api/v1/jobs/workbench');
      document.getElementById('job-todo').innerHTML = `
        <div class="grid c4">
          ${w.items.map((i) => `
            <div class="card tight kpi ${i.count > 0 ? 'accent' : ''}" style="cursor:pointer"
                 onclick="location.hash='#/${i.route}'">
              <span class="label">${U.esc(i.label)}</span>
              <span class="value">${U.int(i.count)}</span>
              <span class="foot">${U.esc(i.hint)}</span>
            </div>`).join('')}
        </div>`;
    } catch (err) {
      document.getElementById('job-todo').innerHTML = `<div class="empty">${U.esc(err.message)}</div>`;
    }
  }

  async function loadList() {
    try {
      const d = await API.get('/api/v1/jobs?page_size=30');
      const items = d.items || [];
      const active = items.filter((j) => !j.is_terminal).length;
      document.getElementById('job-kpi').innerHTML =
        U.kpi('排队中', U.int(items.filter((j) => j.status === 'queued').length), '等待 Worker 领取') +
        U.kpi('执行中', U.int(items.filter((j) => j.status === 'running').length), '正在占用 Worker') +
        U.kpi('已成功', U.int(items.filter((j) => j.status === 'succeeded').length), '近 30 条') +
        U.kpi('失败/取消', U.int(items.filter((j) => ['failed', 'dead', 'timeout', 'cancelled'].includes(j.status)).length), '');

      document.getElementById('job-list').innerHTML = `
        <div class="toolbar" id="job-tools">
          ${(d.type_options || []).map((o) => '').join('')}
          <select id="jf-type"><option value="">全部类型</option>
            ${(d.type_options || []).map((o) => `<option value="${o.value}">${U.esc(o.label)}</option>`).join('')}
          </select>
          <select id="jf-status"><option value="">全部状态</option>
            ${(d.status_options || []).map((o) => `<option value="${o.value}">${U.esc(o.label)}</option>`).join('')}
          </select>
          <label style="font-size:12.5px"><input type="checkbox" id="jf-active" /> 仅看进行中</label>
          <span class="spacer"></span>
          <button class="btn ghost" id="jf-retry-all">批量重试失败作业</button>
          <button class="btn ghost" id="jf-refresh">刷新</button>
        </div>
        <table class="tbl"><thead><tr>
          <th>作业</th><th>类型</th><th style="width:26%">进度 / 当前阶段</th>
          <th>状态</th><th>耗时</th><th style="width:150px">操作</th>
        </tr></thead><tbody>
        ${items.length ? items.map(jobRow).join('') : '<tr><td colspan="6"><div class="empty">暂无作业</div></td></tr>'}
        </tbody></table>`;

      document.getElementById('jf-refresh').onclick = loadList;
      document.getElementById('jf-type').onchange = loadList;
      document.getElementById('jf-status').onchange = loadList;
      document.getElementById('jf-retry-all').onclick = async (e) => {
        e.target.disabled = true;
        try {
          const r = await API.post('/api/v1/jobs/bulk-retry', { all_failed: true });
          U.toast(`已重试 ${r.retried.length} 个作业`, 'ok');
          loadList();
        } catch (err) { U.toast(err.message, 'err'); } finally { e.target.disabled = false; }
      };
      // 快照只用于"首次渲染 + 兜底校准"：实时更新交给下面的事件流。
      // 这里刻意**不**再开 setInterval —— 那正是这条路要替换掉的东西。
      ensureStream();
    } catch (err) {
      document.getElementById('job-list').innerHTML = `<div class="empty">${U.esc(err.message)}</div>`;
    }
  }

  /* ---------------------------------------------------------- 实时事件通道
   * 用 SSE 接收作业事件；浏览器不支持或被网关拦截时，API.openJobEvents
   * 内部会自动退回游标轮询。这里只关心两件事：
   *   1) 把事件增量地应用到表格行（不整表重绘，避免正在展开的行被折叠）；
   *   2) 把通道状态显示出来 —— 用户能区分"没有事件"与"通道断了"。
   */
  function setStreamState(state) {
    const el = document.getElementById('job-stream-state');
    if (!el) return;
    const label = {
      connecting: '正在建立实时通道…',
      sse: '实时推送中（SSE）',
      poll: '降级为轮询（每 2.5 秒）',
      closed: '实时通道已关闭',
    }[state.mode] || state.mode;
    const color = state.mode === 'sse' ? '#1a9e6a'
      : state.mode === 'poll' ? '#d08a00'
        : state.mode === 'closed' ? '#9fb0bd' : '#08A6F6';
    el.innerHTML = `<span style="color:${color}">●</span> ${U.esc(label)}`
      + (state.cursor ? ` <span class="mono muted">#${state.cursor}</span>` : '')
      + (state.transport ? ` <span class="muted">（后端 ${U.esc(state.transport)}）</span>` : '')
      + (state.error ? ` <span style="color:#d08a00">${U.esc(state.error)}</span>` : '');
  }

  function applyEventToRow(ev) {
    const row = document.querySelector(`#job-list tr[data-job-id="${ev.job_id}"]`);
    if (!row) return false;
    const bar = row.querySelector('[data-cell="progress"] .bar-fill');
    if (bar) bar.style.width = `${(Number(ev.progress || 0) * 100).toFixed(1)}%`;
    const txt = row.querySelector('[data-cell="progress"] .muted');
    if (txt) txt.textContent = `${U.pct(ev.progress)} · ${ev.stage_text || ''}`;
    const st = row.querySelector('[data-cell="status"]');
    if (st) st.innerHTML = U.statusTag(ev.job_status || 'queued');
    return true;
  }

  function ensureStream() {
    if (window.__shEventStream) return;
    window.__shEventStream = API.openJobEvents({
      onState: setStreamState,
      onEvent: (ev) => {
        const applied = applyEventToRow(ev);
        // 终态事件、或本表没这一行（新提交的作业）→ 拉一次列表把它带进来。
        // 只在这两种情况下回源，避免每条进度事件都触发一次列表请求。
        const terminal = ['succeeded', 'failed', 'cancelled', 'timeout', 'dead']
          .includes(ev.job_status);
        if (!applied || terminal) loadList();
        if (terminal) loadTodo();
      },
    }, { pollIntervalMs: 2500 });
  }

  function jobRow(j) {
    return `<tr data-job-id="${j.id}">
      <td><strong>${U.esc(j.code)}</strong>
        <div class="muted" style="font-size:11.5px">${U.esc(j.title || '')}</div></td>
      <td>${U.tag(j.type_label, 'sky')}</td>
      <td data-cell="progress">
        <div class="bar-track" style="height:8px"><div class="bar-fill" style="width:${(j.progress * 100).toFixed(1)}%"></div></div>
        <div class="muted" style="font-size:11.5px;margin-top:3px">${U.pct(j.progress)} · ${U.esc(j.stage_text || '')}</div>
      </td>
      <td data-cell="status">${U.statusTag(j.status)}
        ${j.attempts > 1 ? `<div class="muted" style="font-size:11px">第 ${j.attempts}/${j.max_attempts} 次</div>` : ''}</td>
      <td class="num">${j.duration_sec ? j.duration_sec.toFixed(1) + 's' : '—'}</td>
      <td>
        <button class="ghost-btn" onclick="window.__jobLog(${j.id})">日志</button>
        ${j.can_cancel ? `<button class="ghost-btn" onclick="window.__jobCancel(${j.id})">取消</button>` : ''}
        ${j.can_retry ? `<button class="ghost-btn" onclick="window.__jobRetry(${j.id})">重试</button>` : ''}
      </td>
    </tr>`;
  }

  window.__jobLog = async (id) => {
    U.modal('作业事件流', U.loading('加载事件'));
    try {
      const d = await API.get(`/api/v1/jobs/${id}`);
      const events = d.events || [];
      const payload = d.payload || {};
      U.modal(`作业 ${d.code} · ${d.status_label}`, `
        <div class="grid c4" style="margin-bottom:12px">
          ${U.kpi('状态', d.status_label)}${U.kpi('进度', U.pct(d.progress))}
          ${U.kpi('耗时', d.duration_sec ? d.duration_sec.toFixed(1) + 's' : '—')}
          ${U.kpi('尝试次数', `${d.attempts}/${d.max_attempts}`)}
        </div>
        ${d.error_text ? `<div class="note" style="border-left-color:#d64545;background:#fdeaea;border-color:#f5c4c4">${U.esc(d.error_text)}</div>` : ''}
        <h4 style="margin-top:12px">事件流</h4>
        ${events.map((e) => `<div class="step"><span class="act">${U.esc(e.at || '')}</span>
          <span class="agent">${U.tag(e.event)}</span>
          <span class="out">${U.esc(e.message || '')}
          ${e.progress ? `<span class="muted">（${U.pct(e.progress)}）</span>` : ''}</span></div>`).join('')}
        <h4 style="margin-top:12px">入队参数</h4>
        <pre class="mono" style="white-space:pre-wrap">${U.esc(JSON.stringify(payload, null, 2)).slice(0, 2000)}</pre>
        ${Object.keys(d.result || {}).length ? `<h4 style="margin-top:12px">执行结果</h4>
        <pre class="mono" style="white-space:pre-wrap">${U.esc(JSON.stringify(d.result, null, 2)).slice(0, 2000)}</pre>` : ''}`);
    } catch (err) { U.modal('加载失败', `<div class="empty">${U.esc(err.message)}</div>`); }
  };
  window.__jobCancel = async (id) => {
    if (!window.confirm('确认取消该作业？已写入的部分结果会保留，作业会停在安全检查点。')) return;
    try { await API.post(`/api/v1/jobs/${id}/cancel`); U.toast('取消请求已提交', 'ok'); loadList(); }
    catch (err) { U.toast(err.message, 'err'); }
  };
  window.__jobRetry = async (id) => {
    try { await API.post(`/api/v1/jobs/${id}/retry`); U.toast('已重新入队', 'ok'); loadList(); }
    catch (err) { U.toast(err.message, 'err'); }
  };

  loadTodo();
  loadList();
}

/* =============================================================== 15 标注工作台 */
function renderWorkbench(root) {
  root.innerHTML = `
    <div class="grid c2" style="margin-bottom:16px">
      <div class="card">
        <h4>标注录入</h4>
        <div class="toolbar">
          <select id="wb-slide" style="min-width:280px"></select>
          <button class="btn" id="wb-load">载入标签</button>
        </div>
        <div id="wb-form" class="muted">选择一张切片以载入其标签定义与已有标注。</div>
      </div>
      <div class="card">
        <h4>质控队列</h4>
        <p class="muted" style="margin:2px 0 10px">质控不通过的标注会被标记返工，返工完成前不进入训练集。</p>
        <div id="wb-qc">${U.loading('')}</div>
      </div>
    </div>
    <div class="card"><h4>一致性概览</h4><div id="wb-consistency">${U.loading('')}</div></div>`;

  API.get('/api/v1/slides?page_size=200').then((d) => {
    document.getElementById('wb-slide').innerHTML = (d.items || []).map((s) =>
      `<option value="${s.id}">${U.esc(s.code)} · ${U.esc(s.case_no)} · ${U.esc(s.status)}</option>`).join('');
  }).catch(() => {});

  document.getElementById('wb-load').onclick = async () => {
    const sid = document.getElementById('wb-slide').value;
    U.closeModal();
    document.getElementById('wb-form').innerHTML = U.loading('载入标签定义');
    try {
      const d = await API.get(`/api/v1/labels/workbench/${sid}`);
      const layerNames = { case: '病例级', slide: '切片级', region: '区域级', cell: '细胞级', qc: '质控层' };
      const groups = {};
      d.schemas.forEach((s) => { (groups[s.layer] = groups[s.layer] || []).push(s); });
      const formHtml = Object.entries(groups).map(([layer, schemas]) => `
        <div style="margin-bottom:14px">
          <div class="section-title" style="font-size:13px">${U.esc(layerNames[layer] || layer)}
            <span class="sub">${schemas.length} 个标签</span></div>
          ${schemas.map((s) => {
            const cur = d.values[s.code] || {};
            const v = cur.value_text || cur.value_num || '';
            let ctrl;
            if (s.allowed_values && s.allowed_values.length) {
              ctrl = `<select data-code="${U.esc(s.code)}" data-type="${U.esc(s.value_type)}">
                <option value="">—</option>
                ${s.allowed_values.map((o) => `<option ${String(v) === String(o) ? 'selected' : ''}>${U.esc(o)}</option>`).join('')}
              </select>`;
            } else {
              ctrl = `<input data-code="${U.esc(s.code)}" data-type="${U.esc(s.value_type)}"
                        value="${U.esc(v)}" placeholder="${s.value_type === 'numeric' ? '数值' : '文本'}" />`;
            }
            return `<label style="display:block;margin:0 0 8px 0">
              <span style="font-size:12.5px">${U.esc(s.name)} <span class="mono muted">${U.esc(s.code)}</span>
              ${s.required_for_registration ? U.tag('注册必备', 'danger') : ''}
              ${cur.annotator_name ? `<span class="muted">已由 ${U.esc(cur.annotator_name)} 填写</span>` : ''}</span>
              <div style="margin-top:3px">${ctrl}</div>
            </label>`;
          }).join('')}
        </div>`).join('');

      document.getElementById('wb-form').innerHTML = `
        <div class="note" style="margin-bottom:12px">
          切片 <strong>${U.esc(d.slide.code)}</strong> · 已填 ${d.filled_count} 项 ·
          ${d.required_missing.length ? `注册必备缺口：${d.required_missing.join('、')}` : '注册必备标签齐备'}
        </div>
        <form id="wb-save-form">${formHtml}
          <div style="display:flex;gap:8px;justify-content:flex-end">
            <button type="button" class="btn ghost" id="wb-qc-submit">保存并入质控</button>
            <button type="submit" class="btn">仅保存</button>
          </div>
          <div id="wb-error" style="color:#d64545;font-size:12.5px;margin-top:8px"></div>
        </form>`;

      const collect = () => {
        const items = [];
        document.querySelectorAll('#wb-save-form [data-code]').forEach((n) => {
          if (n.value === '' || n.value === undefined) return;
          const type = n.getAttribute('data-type');
          const item = { schema_code: n.getAttribute('data-code') };
          if (type === 'numeric') item.value_num = Number(n.value);
          else item.value_text = n.value;
          items.push(item);
        });
        return items;
      };
      const submit = async (autoQc) => {
        const items = collect();
        const errEl = document.getElementById('wb-error');
        if (!items.length) { errEl.textContent = '至少填写一个标签'; return; }
        try {
          const r = await API.post('/api/v1/labels/workbench/save',
            { slide_id: Number(sid), items, auto_submit_qc: autoQc });
          errEl.textContent = '';
          U.toast(`已保存 ${r.applied_count} 项${r.rejected_count ? `，拒绝 ${r.rejected_count} 项` : ''}`, 'ok');
          if (r.rejected_count) {
            errEl.textContent = '被拒绝：' + r.rejected.map((x) => `${x.schema_code} ${x.error}`).join('；');
          }
          if (r.missing_required_labels.length) {
            errEl.textContent += `　注册必备标签仍缺：${r.missing_required_labels.join('、')}`;
          }
          loadQc();
        } catch (err) { errEl.textContent = err.message; }
      };
      document.getElementById('wb-save-form').addEventListener('submit', (e) => { e.preventDefault(); submit(false); });
      document.getElementById('wb-qc-submit').onclick = () => submit(true);
    } catch (err) {
      document.getElementById('wb-form').innerHTML = `<div class="empty">${U.esc(err.message)}</div>`;
    }
  };

  async function loadQc() {
    try {
      const d = await API.get('/api/v1/labels/qc?page_size=10');
      const items = d.items || [];
      document.getElementById('wb-qc').innerHTML = items.length ? `
        <table class="tbl"><thead><tr><th>切片</th><th>类型</th><th>结果</th><th style="width:150px">判定</th></tr></thead>
        <tbody>${items.map((r) => `<tr>
          <td>${U.esc(r.slide_code || '—')}</td><td>${U.esc(r.qc_type)}</td>
          <td>${U.statusTag(r.result)}${r.rework_required ? ' ' + U.tag('需返工', 'danger') : ''}</td>
          <td>
            <button class="ghost-btn" onclick="window.__qc(${r.id},'pass')">通过</button>
            <button class="ghost-btn" onclick="window.__qc(${r.id},'fail')">返工</button>
          </td></tr>`).join('')}</tbody></table>` : U.empty('暂无质控记录');
    } catch (err) {
      document.getElementById('wb-qc').innerHTML = `<div class="empty">${U.esc(err.message)}</div>`;
    }
  }
  window.__qc = async (id, result) => {
    try {
      await API.post(`/api/v1/labels/qc/${id}/decide`, {
        result, score: result === 'pass' ? 0.95 : 0.4,
        defect_types: result === 'pass' ? [] : ['标注不完整'],
      });
      U.toast(result === 'pass' ? '已通过质控' : '已标记返工', 'ok');
      loadQc();
    } catch (err) { U.toast(err.message, 'err'); }
  };

  API.get('/api/v1/labels/overview').then((o) => {
    const c = o.consistency || {};
    document.getElementById('wb-consistency').innerHTML =
      `<div class="grid c4">
        ${U.kpi('标注记录', U.int(o.annotation_total), '')}
        ${U.kpi('一致性样本', U.int(c.sample_count || 0), '')}
        ${U.kpi('质控记录', U.int(o.qc_total), `通过率 ${U.pct(o.qc_pass_rate)}`)}
        ${U.kpi('SOP 审核', `${U.int((o.sop || {}).approved_count)}/${U.int((o.sop || {}).sop_total)}`, '')}
      </div>
      <div class="note" style="margin-top:10px">${U.esc(c.note || '')}</div>`;
  }).catch(() => {});
  loadQc();
}
