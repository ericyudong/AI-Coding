import { Layout, Menu, Dropdown, Avatar, Space, Typography, theme } from 'antd';
import {
  DashboardOutlined,
  FileTextOutlined,
  LaptopOutlined,
  UserOutlined,
  PartitionOutlined,
  CalendarOutlined,
  AuditOutlined,
  TeamOutlined,
  DatabaseOutlined,
  BarChartOutlined,
  SettingOutlined,
  LogoutOutlined,
  ProfileOutlined,
  ApartmentOutlined,
  ShareAltOutlined,
  MailOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

const { Header, Sider, Content } = Layout;

const items = [
  { key: '/', icon: <DashboardOutlined />, label: <Link to="/">工作台</Link> },
  { key: '/requests', icon: <FileTextOutlined />, label: <Link to="/requests">招聘需求</Link> },
  { key: '/jobs', icon: <LaptopOutlined />, label: <Link to="/jobs">职位</Link> },
  { key: '/candidates', icon: <UserOutlined />, label: <Link to="/candidates">候选人</Link> },
  { key: '/pipeline', icon: <PartitionOutlined />, label: <Link to="/pipeline">招聘流程</Link> },
  { key: '/interviews', icon: <CalendarOutlined />, label: <Link to="/interviews">面试</Link> },
  { key: '/offers', icon: <AuditOutlined />, label: <Link to="/offers">Offer</Link> },
  { key: '/onboarding', icon: <TeamOutlined />, label: <Link to="/onboarding">待入职</Link> },
  { key: '/talent-pool', icon: <DatabaseOutlined />, label: <Link to="/talent-pool">人才库</Link> },
  { key: '/standards', icon: <ProfileOutlined />, label: <Link to="/standards">岗位标准</Link> },
  { key: '/flows', icon: <ApartmentOutlined />, label: <Link to="/flows">流程SLA</Link> },
  { key: '/channels', icon: <ShareAltOutlined />, label: <Link to="/channels">渠道</Link> },
  { key: '/messages', icon: <MailOutlined />, label: <Link to="/messages">消息</Link> },
  { key: '/agent', icon: <RobotOutlined />, label: <Link to="/agent">HR Agent</Link> },
  { key: '/reports', icon: <BarChartOutlined />, label: <Link to="/reports">数据分析</Link> },
  { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">系统设置</Link> },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { token: themeToken } = theme.useToken();
  const selected =
    items.find((i) => i.key !== '/' && location.pathname.startsWith(i.key))?.key ||
    (location.pathname === '/' ? '/' : location.pathname);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        theme="light"
        style={{
          borderRight: `1px solid ${themeToken.colorBorderSecondary}`,
          background: 'linear-gradient(180deg, #f7faf8 0%, #ffffff 40%)',
        }}
      >
        <div style={{ padding: '20px 16px 12px', borderBottom: `1px solid ${themeToken.colorBorderSecondary}` }}>
          <Typography.Title level={4} style={{ margin: 0, color: '#1f6b4a', letterSpacing: 0.5 }}>
            RecruitOS
          </Typography.Title>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            招聘管理系统
          </Typography.Text>
        </div>
        <Menu mode="inline" selectedKeys={[selected]} items={items} style={{ borderInlineEnd: 'none', background: 'transparent' }} />
      </Sider>
      <Layout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: `1px solid ${themeToken.colorBorderSecondary}`,
          }}
        >
          <Typography.Text type="secondary">流程闭环 · 数据留痕 · 责任清楚</Typography.Text>
          <Dropdown
            menu={{
              items: [
                {
                  key: 'logout',
                  icon: <LogoutOutlined />,
                  label: '退出登录',
                  onClick: () => {
                    logout();
                    navigate('/login');
                  },
                },
              ],
            }}
          >
            <Space style={{ cursor: 'pointer' }}>
              <Avatar style={{ background: '#1f6b4a' }}>{user?.name?.[0]}</Avatar>
              <span>
                {user?.name}
                <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                  {user?.roleLabel}
                </Typography.Text>
              </span>
            </Space>
          </Dropdown>
        </Header>
        <Content style={{ margin: 20, minHeight: 360 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
