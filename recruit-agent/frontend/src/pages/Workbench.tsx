import { useEffect, useState } from 'react';
import { Card, Col, Row, Statistic, List, Tag, Button, Space, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import api from '../api';
import { TODO_TYPE, canRole } from '../constants';
import { useAuth } from '../auth';

export default function Workbench() {
  const [data, setData] = useState<any>(null);
  const navigate = useNavigate();
  const { user } = useAuth();

  const load = async () => {
    const res = await api.get('/workbench/summary');
    setData(res.data);
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  if (!data) return null;
  const stats = [
    { title: '在招职位', value: data.stats.openJobs, path: '/jobs?status=OPEN' },
    { title: '招聘人数', value: data.stats.recruitingHeadcount, path: '/jobs' },
    { title: '流程中候选人', value: data.stats.inProcess, path: '/pipeline' },
    { title: '已发Offer', value: data.stats.sentOffers, path: '/offers' },
    { title: '待入职', value: data.stats.pendingOnboard, path: '/onboarding' },
    { title: '已入职', value: data.stats.hired, path: '/pipeline?status=HIRED' },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            工作台
          </Typography.Title>
          <Typography.Text type="secondary">你好，{user?.name}。处理待办，推进招聘闭环。</Typography.Text>
        </div>
        <Space>
          {canRole(user!.role, 'HR', 'DEPT_HEAD', 'RECRUIT_LEAD') && (
            <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => navigate('/requests')}>
              新建招聘需求
            </Button>
          )}
          {canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
            <>
              <Button onClick={() => navigate('/candidates')}>新增候选人</Button>
              <Button onClick={() => navigate('/interviews')}>创建面试</Button>
              <Button onClick={() => navigate('/offers')}>创建Offer</Button>
            </>
          )}
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        {stats.map((s) => (
          <Col xs={12} md={8} lg={4} key={s.title}>
            <Card hoverable onClick={() => navigate(s.path)} styles={{ body: { padding: 16 } }}>
              <Statistic title={s.title} value={s.value} />
            </Card>
          </Col>
        ))}
      </Row>

      <Row gutter={16}>
        <Col xs={24} lg={14}>
          <Card title="个人待办">
            <List
              dataSource={data.todos}
              locale={{ emptyText: '暂无待办' }}
              renderItem={(item: any) => (
                <List.Item
                  actions={[
                    <Button
                      type="link"
                      key="go"
                      onClick={() => {
                        const map: Record<string, string> = {
                          APPROVE_REQUEST: `/requests`,
                          SCREEN: `/pipeline`,
                          ARRANGE_INTERVIEW: `/interviews`,
                          EVALUATE: `/interviews/${item.refId}`,
                          APPROVE_OFFER: `/offers`,
                          ONBOARDING: `/onboarding`,
                        };
                        navigate(map[item.type] || '/');
                      }}
                    >
                      处理
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag color="green">{TODO_TYPE[item.type] || item.type}</Tag>
                        {item.title}
                      </Space>
                    }
                    description={item.dueAt ? `最早到期：${dayjs(item.dueAt).format('YYYY-MM-DD HH:mm')}` : '无截止日期'}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
        <Col xs={24} lg={10}>
          <Card title="最近动态">
            <List
              dataSource={data.activities}
              locale={{ emptyText: '暂无动态' }}
              renderItem={(item: any) => (
                <List.Item>
                  <List.Item.Meta
                    title={item.title}
                    description={`${item.actorName || ''} · ${dayjs(item.createdAt).format('MM-DD HH:mm')}`}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </Space>
  );
}
