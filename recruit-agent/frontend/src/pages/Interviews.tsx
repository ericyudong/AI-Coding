import { useEffect, useState } from 'react';
import {
  Button, Card, DatePicker, Form, Input, Modal, Select, Space, Table, Tag, message, Rate, Descriptions,
} from 'antd';
import { useNavigate, useParams } from 'react-router-dom';
import dayjs from 'dayjs';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function InterviewsPage() {
  const [list, setList] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = async () => {
    const [i, a] = await Promise.all([
      api.get('/interviews'),
      api.get('/applications', { params: { status: 'INTERVIEW' } }),
    ]);
    setList(i.data);
    setApps(a.data);
    try {
      setUsers((await api.get('/config/users')).data);
    } catch {
      setUsers([]);
    }
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Card
      title="面试安排"
      extra={
        canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
          <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => setOpen(true)}>
            创建面试
          </Button>
        )
      }
    >
      <Table
        rowKey="id"
        dataSource={list}
        columns={[
          { title: '候选人', dataIndex: ['application', 'candidate', 'name'] },
          { title: '职位', dataIndex: ['application', 'job', 'title'] },
          { title: '轮次', dataIndex: 'roundName' },
          {
            title: '时间',
            render: (_, r) => `${dayjs(r.startTime).format('MM-DD HH:mm')} - ${dayjs(r.endTime).format('HH:mm')}`,
          },
          {
            title: '面试官',
            render: (_, r) => (r.interviewers || []).map((x: any) => x.user.name).join('、'),
          },
          { title: '方式', dataIndex: 'method', render: (m) => ({ ONSITE: '线下', VIDEO: '视频', PHONE: '电话' }[m] || m) },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s) => <Tag>{s}</Tag>,
          },
          {
            title: '操作',
            render: (_, row) => (
              <Space>
                <Button type="link" onClick={() => navigate(`/interviews/${row.id}`)}>
                  详情/评价
                </Button>
                {canRole(user!.role, 'HR') && row.status === 'SCHEDULED' && (
                  <Button
                    type="link"
                    onClick={async () => {
                      await api.post(`/interviews/${row.id}/attendance`, { status: 'COMPLETED' });
                      message.success('已记录到场，请面试官提交评价');
                      load();
                    }}
                  >
                    标记完成
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal title="创建面试" open={open} onCancel={() => setOpen(false)} footer={null} width={640}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ round: 'FIRST', method: 'VIDEO' }}
          onFinish={async (values) => {
            try {
              const payload = {
                ...values,
                startTime: values.range[0].toISOString(),
                endTime: values.range[1].toISOString(),
              };
              delete payload.range;
              await api.post('/interviews', payload);
              message.success('面试已创建');
              setOpen(false);
              form.resetFields();
              load();
            } catch (e: any) {
              if (e.data?.conflicts) {
                Modal.confirm({
                  title: '面试官时间冲突，是否强制继续？',
                  content: e.data.conflicts.map((c: any) => `${c.interviewerName}: ${c.time}`).join('\n'),
                  onOk: async () => {
                    await api.post('/interviews', {
                      ...values,
                      startTime: values.range[0].toISOString(),
                      endTime: values.range[1].toISOString(),
                      forceConflict: true,
                    });
                    message.success('已强制创建');
                    setOpen(false);
                    load();
                  },
                });
              } else message.error(e.message);
            }
          }}
        >
          <Form.Item name="applicationId" label="应聘记录" rules={[{ required: true }]}>
            <Select
              options={apps.map((a) => ({
                value: a.id,
                label: `${a.candidate.name} - ${a.job.title}`,
              }))}
            />
          </Form.Item>
          <Form.Item name="round" label="轮次" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'FIRST', label: '初试' },
                { value: 'SECOND', label: '复试' },
                { value: 'FINAL', label: '终试' },
              ]}
            />
          </Form.Item>
          <Form.Item name="range" label="时间" rules={[{ required: true }]}>
            <DatePicker.RangePicker showTime style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="method" label="方式" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'ONSITE', label: '线下' },
                { value: 'VIDEO', label: '在线视频' },
                { value: 'PHONE', label: '电话' },
              ]}
            />
          </Form.Item>
          <Form.Item noStyle shouldUpdate>
            {({ getFieldValue }) =>
              getFieldValue('method') === 'ONSITE' ? (
                <Form.Item name="location" label="地址" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
              ) : getFieldValue('method') === 'VIDEO' ? (
                <Form.Item name="meetingLink" label="会议链接" rules={[{ required: true }]}>
                  <Input />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item name="interviewerIds" label="面试官" rules={[{ required: true }]}>
            <Select
              mode="multiple"
              options={users
                .filter((u) => ['INTERVIEWER', 'DEPT_HEAD', 'HR'].includes(u.role))
                .map((u) => ({ value: u.id, label: `${u.name}(${u.roleLabel || u.role})` }))}
            />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
            创建并生成通知
          </Button>
        </Form>
      </Modal>
    </Card>
  );
}

export function InterviewDetailPage() {
  const { id } = useParams();
  const [data, setData] = useState<any>(null);
  const [summary, setSummary] = useState<any>(null);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [d, s] = await Promise.all([api.get(`/interviews/${id}`), api.get(`/interviews/${id}/summary`)]);
    setData(d.data);
    setSummary(s.data);
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, [id]);

  if (!data) return null;

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card
        title={`面试详情 · ${data.application.candidate.name} · ${data.roundName}`}
        extra={
          <Space>
            <Button
              onClick={() => {
                Modal.info({
                  title: '通知内容（可复制后线下发送）',
                  content: <Input.TextArea rows={10} value={data.noticeContent} readOnly />,
                  width: 640,
                  onOk: async () => {
                    await api.post(`/interviews/${id}/notice-sent`, {});
                    message.success('已记录发送时间');
                    load();
                  },
                  okText: '标记已发送',
                });
              }}
            >
              复制通知
            </Button>
            {canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
              <Select
                placeholder="轮次结论"
                style={{ width: 160 }}
                options={[
                  { value: 'PASS', label: '通过' },
                  { value: 'ADDITIONAL', label: '追加面试' },
                  { value: 'PENDING', label: '待定' },
                  { value: 'REJECT', label: '淘汰' },
                ]}
                onChange={async (result) => {
                  await api.post(`/interviews/${id}/round-result`, {
                    result,
                    toOffer: result === 'PASS' && data.round === 'FINAL',
                    toPool: result === 'REJECT',
                    reason: result === 'REJECT' ? '面试未通过' : undefined,
                  });
                  message.success('轮次结论已保存');
                  load();
                }}
              />
            )}
          </Space>
        }
      >
        <Descriptions column={2} size="small" bordered>
          <Descriptions.Item label="职位">{data.application.job.title}</Descriptions.Item>
          <Descriptions.Item label="时间">
            {dayjs(data.startTime).format('YYYY-MM-DD HH:mm')} - {dayjs(data.endTime).format('HH:mm')}
          </Descriptions.Item>
          <Descriptions.Item label="方式">{data.method}</Descriptions.Item>
          <Descriptions.Item label="地点/链接">{data.location || data.meetingLink}</Descriptions.Item>
          <Descriptions.Item label="面试官" span={2}>
            {data.interviewers.map((i: any) => i.user.name).join('、')}
          </Descriptions.Item>
          <Descriptions.Item label="轮次结论">{data.roundResult || '-'}</Descriptions.Item>
          <Descriptions.Item label="状态">{data.status}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="提交面试评价（独立评分，提交前不可见他人）">
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            scores: { professional: 3, experience: 3, problemSolving: 3, communication: 3, motivation: 3, values: 3 },
            risks: '暂未发现',
            nextRound: 'YES',
          }}
          onFinish={async (values) => {
            try {
              await api.post(`/interviews/${id}/evaluate`, { ...values, submit: true });
              message.success('评价已提交并锁定');
              load();
            } catch (e: any) {
              message.error(e.message);
            }
          }}
        >
          <Form.Item label="评估维度（1-5分）" required>
            <Space wrap>
              {[
                ['professional', '专业能力'],
                ['experience', '相关经验'],
                ['problemSolving', '问题解决'],
                ['communication', '沟通协作'],
                ['motivation', '动机与稳定性'],
                ['values', '价值观风险'],
              ].map(([k, label]) => (
                <Form.Item key={k} name={['scores', k]} label={label} style={{ marginBottom: 0 }}>
                  <Rate count={5} />
                </Form.Item>
              ))}
            </Space>
          </Form.Item>
          <Form.Item name="strengths" label="优势（至少20字）" rules={[{ required: true, min: 20 }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="risks" label="风险与疑点" rules={[{ required: true }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="overall" label="总体评价（至少30字）" rules={[{ required: true, min: 30 }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space>
            <Form.Item name="conclusion" label="面试结论" rules={[{ required: true }]}>
              <Select
                style={{ width: 160 }}
                options={[
                  { value: 'STRONG_YES', label: '强烈推荐' },
                  { value: 'YES', label: '推荐' },
                  { value: 'PENDING', label: '待定' },
                  { value: 'NO', label: '不推荐' },
                ]}
              />
            </Form.Item>
            <Form.Item name="nextRound" label="建议下一轮" rules={[{ required: true }]}>
              <Select
                style={{ width: 160 }}
                options={[
                  { value: 'YES', label: '是' },
                  { value: 'NO', label: '否' },
                  { value: 'ADDITIONAL', label: '追加验证' },
                ]}
              />
            </Form.Item>
          </Space>
          <Button type="primary" htmlType="submit" style={{ background: '#1f6b4a' }}>
            提交评价
          </Button>
        </Form>
      </Card>

      <Card title="评价汇总（不自动替代用人决策）">
        {summary?.submitted?.length ? (
          <>
            <p>
              平均分：
              {Object.entries(summary.averages || {})
                .map(([k, v]) => `${k}:${v ?? '-'}`)
                .join(' / ')}
            </p>
            {(summary.submitted || []).map((e: any) => (
              <Card key={e.id} size="small" style={{ marginBottom: 8 }} title={`${e.interviewer.name} · ${e.conclusion}`}>
                <p>优势：{e.strengths}</p>
                <p>风险：{e.risks}</p>
                <p>总评：{e.overall}</p>
              </Card>
            ))}
          </>
        ) : (
          <p>暂无已提交评价，或您尚未提交故不可查看他人评价。</p>
        )}
      </Card>
    </Space>
  );
}
