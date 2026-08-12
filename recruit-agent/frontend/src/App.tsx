import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ConfigProvider, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { AuthProvider, useAuth } from './auth';
import AppLayout from './layout/AppLayout';
import LoginPage from './pages/Login';
import Workbench from './pages/Workbench';
import RequestsPage from './pages/Requests';
import JobsPage from './pages/Jobs';
import CandidatesPage from './pages/Candidates';
import PipelinePage from './pages/Pipeline';
import InterviewsPage, { InterviewDetailPage } from './pages/Interviews';
import OffersPage from './pages/Offers';
import OnboardingPage from './pages/Onboarding';
import TalentPoolPage from './pages/TalentPool';
import ReportsPage from './pages/Reports';
import SettingsPage from './pages/Settings';
import StandardsPage from './pages/Standards';
import FlowsPage from './pages/Flows';
import ChannelsPage from './pages/Channels';
import MessagesPage from './pages/Messages';
import AgentPage from './pages/Agent';
import PortalPage from './pages/Portal';

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        token: {
          colorPrimary: '#1f6b4a',
          borderRadius: 8,
          fontFamily: '"Source Han Sans SC", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <AntApp>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/portal/:token" element={<PortalPage />} />
              <Route
                path="/"
                element={
                  <PrivateRoute>
                    <AppLayout />
                  </PrivateRoute>
                }
              >
                <Route index element={<Workbench />} />
                <Route path="requests" element={<RequestsPage />} />
                <Route path="jobs" element={<JobsPage />} />
                <Route path="candidates" element={<CandidatesPage />} />
                <Route path="pipeline" element={<PipelinePage />} />
                <Route path="interviews" element={<InterviewsPage />} />
                <Route path="interviews/:id" element={<InterviewDetailPage />} />
                <Route path="offers" element={<OffersPage />} />
                <Route path="onboarding" element={<OnboardingPage />} />
                <Route path="talent-pool" element={<TalentPoolPage />} />
                <Route path="standards" element={<StandardsPage />} />
                <Route path="flows" element={<FlowsPage />} />
                <Route path="channels" element={<ChannelsPage />} />
                <Route path="messages" element={<MessagesPage />} />
                <Route path="agent" element={<AgentPage />} />
                <Route path="reports" element={<ReportsPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </AntApp>
    </ConfigProvider>
  );
}
