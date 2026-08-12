import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Radio, Select, Space, Typography, message, DatePicker } from 'antd';
import { useParams } from 'react-router-dom';
import dayjs from 'dayjs';
import axios from 'axios';

const publicApi = axios.create({ baseURL: '/api' });

export default function PortalPage() {
  const { token } = useParams();
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState('');

  const load = async () => {
    try {
      const res = await publicApi.get(`/links/portal/${token}`);
      setData(res.data);
      setError('');
    } catch (e: any) {
      setError(e.response?.data?.message || e.message || '链接无效');
    }
  };

  useEffect(() => {
    load();
  }, [token]);

  if (error) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f3f6f4', padding: 24 }}>
        <Card style={{ width: 420 }}>
          <Typography.Title level={4}>无法访问</Typography.Title>
          <Typography.Text type="danger">{error}</Typography.Text>
        </Card>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'linear-gradient(160deg, #eef5f1 0%, #f7faf8 50%, #e8f0ea 100%)',
        padding: '40px 16px',
      }}
    >
      <Card style={{ maxWidth: 640, margin: '0 auto' }}>
        <Typography.Title level={3} style={{ color: '#1f6b4a', marginTop: 0 }}>
          RecruitOS 候选人门户
        </Typography.Title>
        <Typography.Paragraph type="secondary">
          {data.candidateName} · {data.jobTitle || ''} · 链接有效至 {dayjs(data.expiresAt).format('YYYY-MM-DD HH:mm')}
        </Typography.Paragraph>

        {(data.type === 'INTERVIEW_CONFIRM' || data.type === 'SLOT_PICK') && data.interview && (
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Card size="small" title="面试信息">
              <p>轮次：{data.interview.roundName}</p>
              <p>
                时间：{dayjs(data.interview.startTime).format('YYYY-MM-DD HH:mm')} - {dayjs(data.interview.endTime).format('HH:mm')}
              </p>
              <p>方式：{data.interview.method}</p>
              <p>地点/链接：{data.interview.location || data.interview.meetingLink}</p>
            </Card>
            {data.interview.slotOptions?.length > 0 && (
              <Form
                layout="vertical"
                onFinish={async (v) => {
                  const slot = data.interview.slotOptions.find((s: any) => s.label === v.slot);
                  await publicApi.post(`/links/portal/${token}/confirm-interview`, {
                    selectedSlot: v.slot,
                    startTime: slot?.start,
                    endTime: slot?.end,
                  });
                  message.success('已确认面试时间');
                  load();
                }}
              >
                <Form.Item name="slot" label="请选择可参加时间" rules={[{ required: true }]}>
                  <Radio.Group
                    options={data.interview.slotOptions.map((s: any) => ({
                      value: s.label,
                      label: `${s.label} ${dayjs(s.start).format('MM-DD HH:mm')}`,
                    }))}
                  />
                </Form.Item>
                <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
                  确认面试
                </Button>
              </Form>
            )}
            {!data.interview.slotOptions?.length && (
              <Button
                type="primary"
                block
                style={{ background: '#1f6b4a' }}
                onClick={async () => {
                  await publicApi.post(`/links/portal/${token}/confirm-interview`, {});
                  message.success('已确认参加面试');
                  load();
                }}
              >
                确认参加面试
              </Button>
            )}
          </Space>
        )}

        {data.type === 'OFFER_CONFIRM' && data.offer && (
          <Space direction="vertical" style={{ width: '100%' }} size={16}>
            <Card size="small" title="录用信息">
              <p>工作地点：{data.offer.workLocation}</p>
              <p>职级：{data.offer.level || '-'}</p>
              <p>基本工资：{data.offer.baseSalary}</p>
              <p>拟入职：{dayjs(data.offer.expectedHireDate).format('YYYY-MM-DD')}</p>
              <p>其他约定：{data.offer.otherTerms || '无'}</p>
            </Card>
            <Form
              layout="vertical"
              onFinish={async (v) => {
                await publicApi.post(`/links/portal/${token}/confirm-offer`, v);
                message.success(v.result === 'ACCEPTED' ? '已接受Offer' : '已提交拒绝');
                load();
              }}
            >
              <Form.Item name="result" label="请确认" rules={[{ required: true }]}>
                <Radio.Group
                  options={[
                    { value: 'ACCEPTED', label: '接受' },
                    { value: 'DECLINED', label: '拒绝' },
                  ]}
                />
              </Form.Item>
              <Form.Item noStyle shouldUpdate>
                {({ getFieldValue }) =>
                  getFieldValue('result') === 'DECLINED' ? (
                    <Form.Item name="declineReason" label="拒绝原因" rules={[{ required: true }]}>
                      <Select options={['薪酬', '地点', '发展', '竞对Offer', '个人原因'].map((x) => ({ value: x, label: x }))} />
                    </Form.Item>
                  ) : null
                }
              </Form.Item>
              <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
                提交
              </Button>
            </Form>
          </Space>
        )}

        {data.type === 'SUPPLEMENT' && (
          <Form
            layout="vertical"
            onFinish={async (v) => {
              await publicApi.post(`/links/portal/${token}/supplement`, v);
              message.success('资料已提交');
            }}
          >
            <Form.Item name="education" label="最高学历"><Input /></Form.Item>
            <Form.Item name="school" label="毕业院校"><Input /></Form.Item>
            <Form.Item name="city" label="所在城市"><Input /></Form.Item>
            <Form.Item name="expectSalary" label="期望薪资"><Input /></Form.Item>
            <Form.Item name="currentCompany" label="当前公司"><Input /></Form.Item>
            <Form.Item name="currentTitle" label="当前职位"><Input /></Form.Item>
            <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
              提交补充信息
            </Button>
          </Form>
        )}

        <Card size="small" title="体验反馈" style={{ marginTop: 16 }}>
          <Form
            layout="vertical"
            onFinish={async (v) => {
              await publicApi.post(`/links/portal/${token}/feedback`, v);
              message.success('感谢反馈');
            }}
          >
            <Form.Item name="score" label="评分(1-5)">
              <InputNumber min={1} max={5} />
            </Form.Item>
            <Form.Item name="comment" label="意见">
              <Input.TextArea rows={2} />
            </Form.Item>
            <Button htmlType="submit">提交反馈</Button>
          </Form>
        </Card>
      </Card>
    </div>
  );
}
