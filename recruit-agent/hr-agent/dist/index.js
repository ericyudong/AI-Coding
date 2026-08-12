"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const config_1 = require("./config");
const recruitos_1 = require("./recruitos");
const skills = __importStar(require("./skills"));
const app = (0, express_1.default)();
app.use((0, cors_1.default)());
app.use(express_1.default.json({ limit: '2mb' }));
app.get('/health', (_req, res) => {
    res.json({
        ok: true,
        name: 'hr-agent',
        version: '1.0.0',
        llm: (0, config_1.llmEnabled)() ? 'openai-compatible' : 'mock',
        recruitos: config_1.config.recruitosBaseUrl,
    });
});
app.get('/ai/capabilities', (_req, res) => {
    res.json({
        capabilities: [
            { key: 'jd', name: '职位需求诊断与JD生成', startable: true, path: 'POST /ai/jd/generate' },
            { key: 'publish', name: 'JD多渠道发布文案', startable: true, path: 'POST /ai/jd/publish-pack' },
            { key: 'sourcing', name: 'AI寻聘助手（站内寻访）', startable: true, path: 'POST /ai/sourcing/run' },
            { key: 'resume', name: '简历解析与初筛', startable: true, path: 'POST /ai/resume/parse|/screen' },
            { key: 'talent', name: '人才库推荐与激活', startable: true, path: 'POST /ai/talent/recommend' },
            { key: 'schedule', name: '面试日程协调', startable: true, path: 'POST /ai/interview/schedule-assist' },
            { key: 'ai_interview', name: 'AI面试与多模态测评（文本增强版）', startable: true, path: 'POST /ai/interview/multimodal-assess' },
            { key: 'eval', name: '面试评价汇总', startable: true, path: 'POST /ai/interview/summary' },
            { key: 'nurture', name: '候选人沟通体验', startable: true, path: 'POST /ai/nurture/reply' },
            { key: 'offer', name: 'Offer与入职衔接草稿', startable: true, path: 'POST /ai/offer/draft' },
            { key: 'analytics', name: '招聘数据智能分析', startable: true, path: 'POST /ai/analytics/ask' },
            { key: 'chat', name: '通用对话', startable: true, path: 'POST /ai/chat' },
        ],
    });
});
function withRos(req, res) {
    try {
        return (0, recruitos_1.clientFromAuthHeader)(req.headers.authorization);
    }
    catch (e) {
        res.status(401).json({ message: e.message });
        return null;
    }
}
async function run(res, fn) {
    try {
        const data = await fn();
        res.json(data);
    }
    catch (e) {
        console.error('[hr-agent]', e);
        res.status(500).json({ message: e.message || 'HR Agent 处理失败' });
    }
}
app.post('/ai/jd/generate', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    run(res, () => skills.generateJd(ros, req.body || {}));
});
app.post('/ai/jd/publish-pack', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.jobId)
        return res.status(400).json({ message: 'jobId 必填' });
    run(res, () => skills.publishPack(ros, req.body));
});
app.post('/ai/resume/parse', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.candidateId)
        return res.status(400).json({ message: 'candidateId 必填' });
    run(res, () => skills.parseResume(ros, req.body));
});
app.post('/ai/resume/screen', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.candidateId || !req.body?.jobId) {
        return res.status(400).json({ message: 'candidateId 与 jobId 必填' });
    }
    run(res, () => skills.screenResume(ros, req.body));
});
app.post('/ai/talent/recommend', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.jobId)
        return res.status(400).json({ message: 'jobId 必填' });
    run(res, () => skills.recommendTalent(ros, req.body));
});
app.post('/ai/sourcing/run', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.jobId)
        return res.status(400).json({ message: 'jobId 必填' });
    run(res, () => skills.sourcingAssistant(ros, req.body));
});
app.post('/ai/interview/schedule-assist', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    run(res, () => skills.scheduleAssist(ros, req.body || {}));
});
app.post('/ai/interview/summary', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.applicationId)
        return res.status(400).json({ message: 'applicationId 必填' });
    run(res, () => skills.interviewSummary(ros, req.body));
});
app.post('/ai/interview/multimodal-assess', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.applicationId)
        return res.status(400).json({ message: 'applicationId 必填' });
    run(res, () => skills.multimodalInterviewAssess(ros, req.body));
});
app.post('/ai/nurture/reply', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.question)
        return res.status(400).json({ message: 'question 必填' });
    run(res, () => skills.nurtureReply(ros, req.body));
});
app.post('/ai/offer/draft', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.applicationId)
        return res.status(400).json({ message: 'applicationId 必填' });
    run(res, () => skills.offerDraft(ros, req.body));
});
app.post('/ai/analytics/ask', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.question)
        return res.status(400).json({ message: 'question 必填' });
    run(res, () => skills.analyticsAsk(ros, req.body));
});
app.post('/ai/chat', (req, res) => {
    const ros = withRos(req, res);
    if (!ros)
        return;
    if (!req.body?.message)
        return res.status(400).json({ message: 'message 必填' });
    run(res, () => skills.chat(ros, req.body));
});
app.listen(config_1.config.port, '127.0.0.1', () => {
    console.log(`HR Agent running at http://127.0.0.1:${config_1.config.port} (llm=${(0, config_1.llmEnabled)() ? 'on' : 'mock'})`);
});
