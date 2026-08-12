import './loadEnv';
import express from 'express';
import cors from 'cors';
import path from 'path';
import authRoutes from './routes/auth';
import workbenchRoutes from './routes/workbench';
import requestRoutes from './routes/requests';
import jobRoutes from './routes/jobs';
import candidateRoutes from './routes/candidates';
import applicationRoutes from './routes/applications';
import interviewRoutes from './routes/interviews';
import offerRoutes from './routes/offers';
import onboardingRoutes from './routes/onboarding';
import talentPoolRoutes from './routes/talentPool';
import reportRoutes from './routes/reports';
import configRoutes from './routes/config';
import standardsRoutes from './routes/standards';
import flowsRoutes from './routes/flows';
import channelsRoutes from './routes/channels';
import portalRoutes from './routes/portal';
import messagesRoutes from './routes/messages';
import agentRoutes from './routes/agent';
import phase2Routes from './routes/phase2';
import aiRoutes from './routes/ai';

const app = express();
const PORT = Number(process.env.PORT || 3001);
const HR_AGENT_URL = process.env.HR_AGENT_URL || 'http://127.0.0.1:3002';

app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use('/uploads', express.static(path.join(__dirname, '../uploads')));

app.get('/api/health', (_req, res) =>
  res.json({
    ok: true,
    name: 'recruit-agent',
    version: '2.1.0',
    phase: 'phase2+hr-agent',
    hrAgentUrl: HR_AGENT_URL,
  })
);

app.use('/api/auth', authRoutes);
app.use('/api/workbench', workbenchRoutes);
app.use('/api/requests', requestRoutes);
app.use('/api/jobs', jobRoutes);
app.use('/api/candidates', candidateRoutes);
app.use('/api/applications', applicationRoutes);
app.use('/api/interviews', interviewRoutes);
app.use('/api/offers', offerRoutes);
app.use('/api/onboarding', onboardingRoutes);
app.use('/api/talent-pool', talentPoolRoutes);
app.use('/api/reports', reportRoutes);
app.use('/api/config', configRoutes);

// Phase 2
app.use('/api/standards', standardsRoutes);
app.use('/api/flows', flowsRoutes);
app.use('/api/channels', channelsRoutes);
app.use('/api/links', portalRoutes);
app.use('/api/messages', messagesRoutes);
app.use('/api/agent', agentRoutes);
app.use('/api/p2', phase2Routes);
app.use('/api/ai', aiRoutes);

app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err);
  res.status(500).json({ message: err.message || '服务器错误' });
});

app.listen(PORT, () => {
  console.log(`Recruit Agent API v2 running at http://localhost:${PORT}`);
});
