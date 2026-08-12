/**
 * OCR测试平台前端脚本
 */

const API_BASE = '';  // 同源部署，无需前缀

// 全局状态
const state = {
    files: [],
    currentEngine: 'tesseract',
    config: null,
    lastResult: null  // 保存最近一次识别结果（用于导出Word）
};

// ==================== 页面导航 ====================

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const pages = document.querySelectorAll('.page');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const pageId = item.dataset.page;

            // 更新导航激活状态
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            // 更新页面显示状态
            pages.forEach(page => page.classList.remove('active'));
            document.getElementById(pageId + 'Page').classList.add('active');

            // 页面切换时加载数据
            if (pageId === 'config') {
                loadConfig();
                loadEngineStatus();
            } else if (pageId === 'history') {
                loadHistory();
            }
        });
    });
}

// ==================== 文件上传 ====================

function initUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');

    // 点击上传
    uploadArea.addEventListener('click', () => {
        fileInput.click();
    });

    // 文件选择
    fileInput.addEventListener('change', (e) => {
        addFiles(Array.from(e.target.files));
        fileInput.value = '';
    });

    // 拖拽上传
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
        addFiles(Array.from(e.dataTransfer.files));
    });

    // 开始识别按钮
    document.getElementById('startOcrBtn').addEventListener('click', startOCR);
}

function isPdfFile(file) {
    return file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
}

function addFiles(files) {
    const allowedTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/tiff', 'image/bmp', 'image/gif', 'application/pdf'];
    
    files.forEach(file => {
        // 检查文件类型（支持MIME类型和扩展名判断）
        const isAllowed = allowedTypes.includes(file.type) || 
                         /\.(png|jpe?g|tiff?|bmp|gif|pdf)$/i.test(file.name);
        if (!isAllowed) {
            showToast(`不支持的文件类型: ${file.name}`, 'error');
            return;
        }
        if (file.size > 50 * 1024 * 1024) {
            showToast(`文件过大: ${file.name}`, 'error');
            return;
        }
        state.files.push(file);
    });

    renderFileList();
}

function renderFileList() {
    const fileList = document.getElementById('fileList');
    const fileItems = document.getElementById('fileItems');

    if (state.files.length === 0) {
        fileList.style.display = 'none';
        return;
    }

    fileList.style.display = 'block';
    fileItems.innerHTML = '';

    state.files.forEach((file, index) => {
        const item = document.createElement('div');
        item.className = 'file-item';
        
        // PDF文件显示图标，图片文件显示预览
        if (isPdfFile(file)) {
            const pdfIcon = document.createElement('div');
            pdfIcon.className = 'file-item-pdf-icon';
            pdfIcon.innerHTML = `
                <svg viewBox="0 0 24 24" width="40" height="40" fill="#e53e3e">
                    <path d="M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm-1 7V3.5L18.5 9H13zM6 20V4h5v7h7v9H6z"/>
                    <text x="7" y="17" font-size="6" fill="#e53e3e" font-weight="bold">PDF</text>
                </svg>
            `;
            item.appendChild(pdfIcon);
        } else {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.onload = () => URL.revokeObjectURL(img.src);
            item.appendChild(img);
        }

        const info = document.createElement('div');
        info.className = 'file-item-info';
        info.innerHTML = `
            <div class="file-item-name">${file.name}</div>
            <div class="file-item-size">${formatFileSize(file.size)}${isPdfFile(file) ? ' · PDF' : ''}</div>
        `;

        const removeBtn = document.createElement('button');
        removeBtn.className = 'file-item-remove';
        removeBtn.innerHTML = '✕';
        removeBtn.onclick = () => {
            state.files.splice(index, 1);
            renderFileList();
        };

        item.appendChild(info);
        item.appendChild(removeBtn);
        fileItems.appendChild(item);
    });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

async function startOCR() {
    if (state.files.length === 0) return;

    const loading = document.getElementById('loadingOverlay');
    const engineSelect = document.getElementById('engineSelect');
    const engine = engineSelect.value || null;

    loading.style.display = 'flex';

    try {
        // 逐个处理文件（简化版，生产环境可用批量接口）
        for (const file of state.files) {
            const formData = new FormData();
            formData.append('file', file);
            if (engine) {
                formData.append('engine', engine);
            }

            const response = await fetch(`${API_BASE}/api/ocr/upload`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '识别失败');
            }

            const data = await response.json();
            showResult(data, file);
        }

        state.files = [];
        renderFileList();
        showToast('识别完成', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        loading.style.display = 'none';
    }
}

function showResult(data, file) {
    const resultSection = document.getElementById('resultSection');
    const resultImage = document.getElementById('resultImage');
    const resultImageTitle = document.getElementById('resultImageTitle');
    const resultPdfPreview = document.getElementById('resultPdfPreview');
    const resultText = document.getElementById('resultText');
    const resultEngine = document.getElementById('resultEngine');
    const resultConfidence = document.getElementById('resultConfidence');
    const resultTime = document.getElementById('resultTime');

    resultSection.style.display = 'block';
    
    // PDF文件显示PDF预览面板，图片文件显示图片预览
    if (data.is_pdf) {
        resultImage.style.display = 'none';
        resultPdfPreview.style.display = 'flex';
        resultImageTitle.textContent = `PDF文档 (${data.total_pages} 页)`;
        document.getElementById('pdfPreviewName').textContent = data.filename || file.name;
        document.getElementById('pdfPreviewPages').textContent = `共 ${data.total_pages} 页`;
    } else {
        resultImage.style.display = 'block';
        resultPdfPreview.style.display = 'none';
        resultImage.src = URL.createObjectURL(file);
        resultImageTitle.textContent = '原始图片';
    }
    
    resultText.value = data.result.text || '（未识别到文字）';
    resultEngine.textContent = data.result.engine;
    resultConfidence.textContent = (data.result.confidence * 100).toFixed(1) + '%';
    resultTime.textContent = data.result.processing_time.toFixed(2) + 's';

    // 保存最近一次识别结果（用于导出Word）
    state.lastResult = {
        text: data.result.text || '',
        filename: data.filename || file.name,
        engine: data.result.engine || '',
        confidence: data.result.confidence || 0,
        processing_time: data.result.processing_time || 0,
        is_pdf: data.is_pdf || false,
        total_pages: data.total_pages || 0
    };

    // 滚动到结果区域
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

// ==================== 结果操作 ====================

function initResultActions() {
    // 复制文本
    document.getElementById('copyTextBtn').addEventListener('click', async () => {
        const text = document.getElementById('resultText').value;
        try {
            await navigator.clipboard.writeText(text);
            showToast('已复制到剪贴板', 'success');
        } catch {
            // 降级方案
            const textarea = document.getElementById('resultText');
            textarea.select();
            document.execCommand('copy');
            showToast('已复制到剪贴板', 'success');
        }
    });

    // 下载文本
    document.getElementById('downloadTextBtn').addEventListener('click', () => {
        const text = document.getElementById('resultText').value;
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'ocr_result.txt';
        a.click();
        URL.revokeObjectURL(url);
        showToast('文本已下载', 'success');
    });

    // 下载Word
    document.getElementById('downloadWordBtn').addEventListener('click', downloadWord);
}

async function downloadWord() {
    const text = document.getElementById('resultText').value;
    if (!text) {
        showToast('没有可导出的识别文本', 'error');
        return;
    }

    const btn = document.getElementById('downloadWordBtn');
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '生成中...';

    try {
        const payload = {
            text: text,
            filename: state.lastResult?.filename || 'OCR识别结果',
            engine: state.lastResult?.engine || '',
            confidence: state.lastResult?.confidence || 0,
            processing_time: state.lastResult?.processing_time || 0,
            is_pdf: state.lastResult?.is_pdf || false,
            total_pages: state.lastResult?.total_pages || 0
        };

        const response = await fetch(`${API_BASE}/api/ocr/export-word`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '导出失败');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // 从Content-Disposition获取文件名，若失败则用默认名
        const disposition = response.headers.get('Content-Disposition');
        let docName = 'OCR识别结果.docx';
        if (disposition) {
            const match = disposition.match(/filename="?([^"]+)"?/);
            if (match && match[1]) {
                docName = decodeURIComponent(match[1]);
            }
        }
        a.download = docName;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Word文档已下载', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
    }
}

// ==================== 配置管理 ====================

async function loadConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        const config = await response.json();
        state.config = config;

        // 填充Tesseract配置
        document.getElementById('tesseractPath').value = config.tesseract?.path || '';
        document.getElementById('tesseractLang').value = config.tesseract?.lang || 'chi_sim+eng';
        document.getElementById('tesseractPsm').value = config.tesseract?.psm || 3;
        document.getElementById('tesseractOem').value = config.tesseract?.oem || 3;

        // 填充PaddleOCR配置
        document.getElementById('paddleLang').value = config.paddleocr?.lang || 'ch';
        document.getElementById('paddleUseGpu').checked = config.paddleocr?.use_gpu || false;
        document.getElementById('paddleUseAngleCls').checked = config.paddleocr?.use_angle_cls !== false;

        // 填充EasyOCR配置
        const easyocrLangs = config.easyocr?.lang_list || ['ch_sim', 'en'];
        document.querySelectorAll('.easyocr-lang').forEach(checkbox => {
            checkbox.checked = easyocrLangs.includes(checkbox.value);
        });
        document.getElementById('easyocrUseGpu').checked = config.easyocr?.gpu || false;

        // 填充OvisOCR配置
        document.getElementById('ovisocrModelId').value = config.ovisocr?.model_id || '';
        document.getElementById('ovisocrApiUrl').value = config.ovisocr?.api_url || '';
        document.getElementById('ovisocrApiKey').value = config.ovisocr?.api_key || '';

        // 填充通用配置
        document.getElementById('preprocessEnabled').checked = config.general?.preprocess !== false;
        document.getElementById('denoiseEnabled').checked = config.general?.denoise !== false;
        document.getElementById('thresholdEnabled').checked = config.general?.threshold !== false;
    } catch (error) {
        showToast('加载配置失败', 'error');
    }
}

async function loadEngineStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/engines/status`);
        const data = await response.json();

        const statusList = document.getElementById('engineStatusList');
        statusList.innerHTML = '';

        const engineNames = {
            tesseract: 'Tesseract OCR',
            paddleocr: 'PaddleOCR',
            easyocr: 'EasyOCR',
            ovisocr: 'OvisOCR'
        };

        for (const [name, info] of Object.entries(data.engines)) {
            const item = document.createElement('div');
            item.className = 'engine-status-item';
            
            const isCurrent = data.current_engine === name;
            const badgeClass = info.available ? 'available' : 'unavailable';
            const badgeText = info.available ? (isCurrent ? '当前使用' : '可用') : '未安装';

            item.innerHTML = `
                <span class="engine-name">${engineNames[name] || name}</span>
                <div>
                    <span class="engine-badge ${badgeClass}">${badgeText}</span>
                    ${info.available && !isCurrent ? `<button class="btn btn-secondary" style="margin-left: 8px; padding: 4px 12px;" onclick="switchEngine('${name}')">设为默认</button>` : ''}
                </div>
            `;
            statusList.appendChild(item);
        }

        // 更新侧边栏状态
        updateSidebarEngineStatus(data.current_engine, data.engines[data.current_engine]?.available);
    } catch (error) {
        console.error('加载引擎状态失败:', error);
    }
}

async function switchEngine(engineName) {
    try {
        const formData = new FormData();
        formData.append('engine_name', engineName);

        const response = await fetch(`${API_BASE}/api/config/engine`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '切换失败');
        }

        showToast(`已切换到 ${engineName}`, 'success');
        loadEngineStatus();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

function updateSidebarEngineStatus(engineName, available) {
    const statusDot = document.getElementById('engineStatusDot');
    const nameSpan = document.getElementById('currentEngineName');

    const displayNames = {
        tesseract: 'Tesseract',
        paddleocr: 'PaddleOCR',
        easyocr: 'EasyOCR',
        ovisocr: 'OvisOCR'
    };

    nameSpan.textContent = displayNames[engineName] || engineName;
    statusDot.classList.toggle('offline', !available);
}

async function saveConfig() {
    // 收集EasyOCR语言
    const easyocrLangs = Array.from(document.querySelectorAll('.easyocr-lang:checked'))
        .map(cb => cb.value);

    const config = {
        tesseract: {
            path: document.getElementById('tesseractPath').value,
            lang: document.getElementById('tesseractLang').value,
            psm: parseInt(document.getElementById('tesseractPsm').value),
            oem: parseInt(document.getElementById('tesseractOem').value)
        },
        paddleocr: {
            lang: document.getElementById('paddleLang').value,
            use_gpu: document.getElementById('paddleUseGpu').checked,
            use_angle_cls: document.getElementById('paddleUseAngleCls').checked
        },
        easyocr: {
            lang_list: easyocrLangs,
            gpu: document.getElementById('easyocrUseGpu').checked
        },
        ovisocr: {
            model_id: document.getElementById('ovisocrModelId').value,
            api_url: document.getElementById('ovisocrApiUrl').value,
            api_key: document.getElementById('ovisocrApiKey').value
        },
        general: {
            preprocess: document.getElementById('preprocessEnabled').checked,
            denoise: document.getElementById('denoiseEnabled').checked,
            threshold: document.getElementById('thresholdEnabled').checked
        }
    };

    try {
        const response = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        if (!response.ok) {
            throw new Error('保存失败');
        }

        showToast('配置已保存', 'success');
        loadEngineStatus();
    } catch (error) {
        showToast('保存配置失败', 'error');
    }
}

function initConfig() {
    document.getElementById('saveConfigBtn').addEventListener('click', saveConfig);
    document.getElementById('resetConfigBtn').addEventListener('click', () => {
        if (confirm('确定要重置为默认配置吗？')) {
            localStorage.removeItem('ocr_config');
            loadConfig();
            showToast('配置已重置', 'success');
        }
    });
}

// ==================== 历史记录 ====================

async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/history`);
        const data = await response.json();

        const historyList = document.getElementById('historyList');
        historyList.innerHTML = '';

        if (data.history.length === 0) {
            historyList.innerHTML = '<div class="history-empty">暂无识别记录</div>';
            return;
        }

        data.history.forEach(item => {
            const historyItem = document.createElement('div');
            historyItem.className = 'history-item';
            
            const time = new Date(item.timestamp).toLocaleString('zh-CN');
            const pdfBadge = item.is_pdf ? `<span class="history-pdf-badge">PDF ${item.pages || ''}页</span>` : '';
            
            historyItem.innerHTML = `
                <div class="history-item-info">
                    <div class="history-item-filename">${item.filename} ${pdfBadge}</div>
                    <div class="history-item-meta">
                        <span>引擎: ${item.engine}</span>
                        <span>置信度: ${(item.confidence * 100).toFixed(1)}%</span>
                        <span>耗时: ${item.processing_time.toFixed(2)}s</span>
                        <span>${time}</span>
                    </div>
                    <div class="history-item-preview">${item.text_preview || '（无文字）'}</div>
                </div>
                <div class="history-item-actions">
                    <button class="btn btn-secondary history-view-btn" data-id="${item.id}">查看</button>
                    <button class="btn btn-primary history-word-btn" data-id="${item.id}">Word</button>
                </div>
            `;
            historyList.appendChild(historyItem);
        });

        // 绑定查看按钮事件
        historyList.querySelectorAll('.history-view-btn').forEach(btn => {
            btn.addEventListener('click', () => viewHistoryItem(btn.dataset.id));
        });

        // 绑定Word导出按钮事件
        historyList.querySelectorAll('.history-word-btn').forEach(btn => {
            btn.addEventListener('click', () => exportHistoryWord(btn.dataset.id));
        });
    } catch (error) {
        showToast('加载历史失败', 'error');
    }
}

async function viewHistoryItem(id) {
    try {
        const response = await fetch(`${API_BASE}/api/history/${id}`);
        if (!response.ok) throw new Error('加载历史记录失败');
        const data = await response.json();
        showHistoryModal(data.item);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

function showHistoryModal(item) {
    const existing = document.getElementById('historyModal');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.id = 'historyModal';

    const time = new Date(item.timestamp).toLocaleString('zh-CN');
    const pdfBadge = item.is_pdf ? `<span class="history-pdf-badge">PDF ${item.pages || ''}页</span>` : '';
    const amp = String.fromCharCode(38);
    const lt = String.fromCharCode(60);
    const safeText = (item.full_text || item.text_preview || '').split(amp).join(amp + 'amp;').split(lt).join(amp + 'lt;');

    overlay.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <div>
                    <div class="modal-title">${item.filename} ${pdfBadge}</div>
                    <div class="modal-meta">引擎: ${item.engine} · 置信度: ${(item.confidence * 100).toFixed(1)}% · 耗时: ${item.processing_time.toFixed(2)}s · ${time}</div>
                </div>
                <button class="modal-close" id="modalCloseBtn">✕</button>
            </div>
            <textarea class="modal-text" id="modalText" readonly>${safeText}</textarea>
            <div class="modal-actions">
                <button class="btn btn-secondary" id="modalCopyBtn">复制文本</button>
                <button class="btn btn-primary" id="modalWordBtn">下载Word</button>
            </div>
        </div>
    `;

    document.body.appendChild(overlay);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.getElementById('modalCloseBtn').addEventListener('click', () => overlay.remove());

    document.getElementById('modalCopyBtn').addEventListener('click', async () => {
        const text = document.getElementById('modalText').value;
        try {
            await navigator.clipboard.writeText(text);
            showToast('已复制到剪贴板', 'success');
        } catch {
            const ta = document.getElementById('modalText');
            ta.select();
            document.execCommand('copy');
            showToast('已复制到剪贴板', 'success');
        }
    });

    document.getElementById('modalWordBtn').addEventListener('click', () => exportItemWord(item));
}

async function exportHistoryWord(id) {
    try {
        const response = await fetch(`${API_BASE}/api/history/${id}`);
        if (!response.ok) throw new Error('加载历史记录失败');
        const data = await response.json();
        await exportItemWord(data.item);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function exportItemWord(item) {
    try {
        const payload = {
            text: item.full_text || item.text_preview || '',
            filename: item.filename || 'OCR识别结果',
            engine: item.engine || '',
            confidence: item.confidence || 0,
            processing_time: item.processing_time || 0,
            is_pdf: item.is_pdf || false,
            total_pages: item.pages || 0
        };

        const response = await fetch(`${API_BASE}/api/ocr/export-word`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '导出失败');
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(item.filename || 'OCR识别结果').replace(/\.[^.]+$/, '')}_OCR结果.docx`;
        a.click();
        URL.revokeObjectURL(url);
        showToast('Word文档已下载', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

function initHistory() {
    document.getElementById('refreshHistoryBtn').addEventListener('click', loadHistory);
    document.getElementById('clearHistoryBtn').addEventListener('click', async () => {
        if (!confirm('确定要清空所有历史记录吗？')) return;

        try {
            await fetch(`${API_BASE}/api/history`, { method: 'DELETE' });
            loadHistory();
            showToast('历史已清空', 'success');
        } catch (error) {
            showToast('清空失败', 'error');
        }
    });
}

// ==================== 工具函数 ====================

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// ==================== 初始化 ====================

async function init() {
    initNavigation();
    initUpload();
    initResultActions();
    initConfig();
    initHistory();

    // 加载引擎状态
    try {
        const response = await fetch(`${API_BASE}/api/engines`);
        const data = await response.json();
        state.currentEngine = data.current_engine;
        
        const currentEngineInfo = data.engines.find(e => e.name === data.current_engine);
        updateSidebarEngineStatus(data.current_engine, currentEngineInfo?.available);
    } catch (error) {
        console.error('初始化失败:', error);
        updateSidebarEngineStatus('tesseract', false);
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);