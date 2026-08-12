import { Router } from 'express';
import { authRequired } from '../middleware/auth';
import { callHrAgent, hrAgentHealth, getHrAgentUrl } from '../services/hrAgentClient';
import { writeAudit } from '../utils/helpers';

const router = Router();

function bearer(req: any): string {
  const h = req.headers.authorization || '';
  return h.startsWith('Bearer ') ? h.slice(7) : '';
}

router.get('/health', authRequired, async (_req, res) => {
  res.json(await hrAgentHealth());
});

router.get('/capabilities', authRequired, async (req, res) => {
  try {
    const data = await callHrAgent('/ai/capabilities', { method: 'GET', token: bearer(req) });
    res.json(data);
  } catch (e: any) {
    res.status(503).json({ message: e.message || 'HR Agent 不可用', url: getHrAgentUrl() });
  }
});

async function proxy(req: any, res: any, path: string) {
  try {
    const data = await callHrAgent(path, { method: 'POST', token: bearer(req), body: req.body || {} });
    await writeAudit(req, `AI:${path}`, 'HrAgent', path, null, { keys: Object.keys(req.body || {}) });
    res.json(data);
  } catch (e: any) {
    const status = /不可用|ECONNREFUSED|fetch failed|abort/i.test(e.message) ? 503 : 500;
    res.status(status).json({ message: e.message || '调用 HR Agent 失败', url: getHrAgentUrl() });
  }
}

router.post('/chat', authRequired, (req, res) => proxy(req, res, '/ai/chat'));
router.post('/jd/generate', authRequired, (req, res) => proxy(req, res, '/ai/jd/generate'));
router.post('/jd/publish-pack', authRequired, (req, res) => proxy(req, res, '/ai/jd/publish-pack'));
router.post('/resume/parse', authRequired, (req, res) => proxy(req, res, '/ai/resume/parse'));
router.post('/resume/screen', authRequired, (req, res) => proxy(req, res, '/ai/resume/screen'));
router.post('/talent/recommend', authRequired, (req, res) => proxy(req, res, '/ai/talent/recommend'));
router.post('/sourcing/run', authRequired, (req, res) => proxy(req, res, '/ai/sourcing/run'));
router.post('/interview/schedule-assist', authRequired, (req, res) => proxy(req, res, '/ai/interview/schedule-assist'));
router.post('/interview/summary', authRequired, (req, res) => proxy(req, res, '/ai/interview/summary'));
router.post('/interview/multimodal-assess', authRequired, (req, res) => proxy(req, res, '/ai/interview/multimodal-assess'));
router.post('/nurture/reply', authRequired, (req, res) => proxy(req, res, '/ai/nurture/reply'));
router.post('/offer/draft', authRequired, (req, res) => proxy(req, res, '/ai/offer/draft'));
router.post('/analytics/ask', authRequired, (req, res) => proxy(req, res, '/ai/analytics/ask'));

export default router;
