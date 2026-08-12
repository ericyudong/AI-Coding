import { useState } from 'react';
import { Button, Card, Form, Input, Typography, message, Space, Tag } from 'antd';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { useAuth } from '../auth';

const demos = [
  { u: 'hr', label: '招聘HR' },
  { u: 'lead', label: '招聘负责人' },
  { u: 'dept', label: '部门负责人' },
  { u: 'interviewer', label: '面试官' },
  { u: 'approver', label: 'Offer审批' },
  { u: 'ops', label: '人事运营' },
  { u: 'admin', label: '管理员' },
];

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const onFinish = async (values: { username: string; password: string }) => {
    setLoading(true);
    try {
      const { data } = await api.post('/auth/login', values);
      login(data.token, data.user);
      message.success(`欢迎，${data.user.name}`);
      navigate('/');
    } catch (e: any) {
      message.error(e.message || '登录失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'grid',
        placeItems: 'center',
        background:
          'radial-gradient(circle at 20% 20%, #d9efe4 0%, transparent 40%), radial-gradient(circle at 80% 0%, #e8f0ea 0%, transparent 35%), linear-gradient(160deg, #f4f7f5 0%, #eef3f0 100%)',
        padding: 24,
      }}
    >
      <Card style={{ width: 420, boxShadow: '0 12px 40px rgba(31,107,74,0.08)' }} styles={{ body: { padding: 32 } }}>
        <Typography.Title level={2} style={{ marginTop: 0, color: '#1f6b4a' }}>
          RecruitOS
        </Typography.Title>
        <Typography.Paragraph type="secondary">招聘管理系统 · 独立于 HR Agent 的基础闭环</Typography.Paragraph>
        <Form layout="vertical" onFinish={onFinish} initialValues={{ username: 'hr', password: '123456' }}>
          <Form.Item name="username" label="用户名" rules={[{ required: true }]}>
            <Input size="large" placeholder="用户名" />
          </Form.Item>
          <Form.Item name="password" label="密码" rules={[{ required: true }]}>
            <Input.Password size="large" placeholder="密码" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block size="large" loading={loading} style={{ background: '#1f6b4a' }}>
            登录
          </Button>
        </Form>
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 16, marginBottom: 8 }}>
          演示账号（密码均为 123456）：
        </Typography.Text>
        <Space wrap>
          {demos.map((d) => (
            <Tag
              key={d.u}
              style={{ cursor: 'pointer' }}
              onClick={() => onFinish({ username: d.u, password: '123456' })}
            >
              {d.label}
            </Tag>
          ))}
        </Space>
      </Card>
    </div>
  );
}
