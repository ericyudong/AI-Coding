import { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, Modal, Select, Space, Table, Tag, Typography, message } from 'antd';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function ChannelsPage() {
  const [channels, setChannels] = useState<any[]>([]);
  const [pubs, setPubs] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [compliance, setCompliance] = useState<any>(null);
  const [adapters, setAdapters] = useState<any[]>([]);
  const [pending, setPending] = useState<any[]>([]);
  const { user } = useAuth();

  const load = async () => {
    const [c, p, j, comp, ad, actions] = await Promise.all([
      api.get('/channels'),
      api.get('/channels/publishes'),
      api.get('/jobs'),
      api.get('/channels/compliance'),
      api.get('/channels/adapters'),
      api.get('/agent/actions', { params: { status: 'PENDING' } }),
    ]);
    setChannels(c.data);
    setPubs(p.data);
    setJobs(j.data.filter((x: any) => x.status === 'OPEN'));
    setCompliance(comp.data);
    setAdapters(ad.data.health || []);
    setPending(
      (actions.data || []).filter((a: any) => ['PUBLISH_CHANNEL', 'EXTERNAL_OUTREACH'].includes(a.actionKey))
    );
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card title="渠道合规与适配层状态">
        {compliance && (
          <Alert
            type={compliance.mode === 'live' ? 'warning' : 'info'}
            showIcon
            style={{ marginBottom: 12 }}
            message={`当前模式：${compliance.mode} · 人工确认闸门：${compliance.requireHumanConfirm ? '开启' : '关闭'} · 外部触达：${
              compliance.externalOutreachEnabled ? '允许' : '关闭'
            }`}
            description={(compliance.notes || []).join('；')}
          />
        )}
        <Table
          size="small"
          rowKey="code"
          pagination={false}
          dataSource={adapters}
          columns={[
            { title: '适配器', dataIndex: 'name' },
            { title: '编码', dataIndex: 'code' },
            { title: '模式', dataIndex: 'mode' },
            {
              title: '健康',
              dataIndex: 'ok',
              render: (ok) => <Tag color={ok ? 'green' : 'red'}>{ok ? 'OK' : '不可用'}</Tag>,
            },
            { title: '说明', dataIndex: 'detail', ellipsis: true },
          ]}
        />
      </Card>

      <Card
        title="人工审核闸门（外部渠道动作）"
        extra={
          <Button onClick={() => load().catch((e) => message.error(e.message))}>刷新</Button>
        }
      >
        <Typography.Paragraph type="secondary">
          发布到 Boss/猎聘、外部打招呼均为高风险动作，需确认后才会调用渠道适配层。
        </Typography.Paragraph>
        <Table
          rowKey="id"
          dataSource={pending}
          locale={{ emptyText: '暂无待确认外部动作' }}
          columns={[
            { title: '动作', dataIndex: 'actionKey', width: 160 },
            {
              title: '内容',
              dataIndex: 'payload',
              ellipsis: true,
              render: (v) => {
                try {
                  const p = JSON.parse(v || '{}');
                  return p.jobTitle || p.candidateName || p.message || v;
                } catch {
                  return v;
                }
              },
            },
            { title: '风险', dataIndex: 'riskLevel', render: (v) => <Tag color="red">{v}</Tag>, width: 80 },
            {
              title: '操作',
              width: 180,
              render: (_, row) =>
                canRole(user!.role, 'HR', 'RECRUIT_LEAD', 'ADMIN') && (
                  <Space>
                    <Button
                      type="link"
                      onClick={async () => {
                        await api.post(`/agent/actions/${row.id}/confirm`, {});
                        message.success('已确认并执行');
                        load();
                      }}
                    >
                      确认执行
                    </Button>
                    <Button
                      type="link"
                      danger
                      onClick={async () => {
                        await api.post(`/agent/actions/${row.id}/confirm`, { reject: true, reason: '不通过' });
                        message.info('已拒绝');
                        load();
                      }}
                    >
                      拒绝
                    </Button>
                  </Space>
                ),
            },
          ]}
        />
      </Card>

      <Card
        title="渠道账号与映射"
        extra={
          canRole(user!.role, 'ADMIN', 'RECRUIT_LEAD') && (
            <Button
              type="primary"
              style={{ background: '#1f6b4a' }}
              onClick={() => {
                let values: any = { type: 'SITE' };
                Modal.confirm({
                  title: '新增渠道',
                  content: (
                    <Form layout="vertical" style={{ marginTop: 12 }} onValuesChange={(_, all) => (values = all)} initialValues={values}>
                      <Form.Item name="name" label="名称" required>
                        <Input />
                      </Form.Item>
                      <Form.Item name="code" label="编码" required>
                        <Input placeholder="BOSS / LIEPIN / REFERRAL" />
                      </Form.Item>
                      <Form.Item name="type" label="类型">
                        <Select options={['SITE', 'REFERRAL', 'HUNTER', 'CAMPUS', 'OTHER'].map((x) => ({ value: x, label: x }))} />
                      </Form.Item>
                      <Form.Item name="accountName" label="账号名">
                        <Input />
                      </Form.Item>
                    </Form>
                  ),
                  onOk: async () => {
                    await api.post('/channels', values);
                    message.success('已创建');
                    load();
                  },
                });
              }}
            >
              新增渠道
            </Button>
          )
        }
      >
        <Table
          rowKey="id"
          dataSource={channels}
          columns={[
            { title: '渠道', dataIndex: 'name' },
            { title: '编码', dataIndex: 'code' },
            { title: '类型', dataIndex: 'type' },
            {
              title: '账号',
              render: (_, r) => (r.accounts || []).map((a: any) => a.accountName).join('、') || '-',
            },
            { title: '发布数', dataIndex: ['_count', 'publishes'] },
          ]}
        />
      </Card>

      <Card
        title="职位渠道发布"
        extra={
          canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
            <Button
              onClick={() => {
                Modal.confirm({
                  title: '发布到外部渠道（将进入人工确认）',
                  content: (
                    <Space direction="vertical" style={{ width: '100%', marginTop: 12 }}>
                      <Select
                        placeholder="职位"
                        style={{ width: '100%' }}
                        options={jobs.map((j) => ({ value: j.id, label: j.title }))}
                        onChange={(v) => ((Modal as any)._jobId = v)}
                      />
                      <Select
                        placeholder="渠道"
                        style={{ width: '100%' }}
                        options={channels.map((c) => ({ value: c.id, label: `${c.name} (${c.code})` }))}
                        onChange={(v) => ((Modal as any)._channelId = v)}
                      />
                    </Space>
                  ),
                  onOk: async () => {
                    try {
                      const { data, status } = await api.post(
                        '/channels/publish',
                        {
                          jobId: (Modal as any)._jobId,
                          channelId: (Modal as any)._channelId,
                        },
                        { validateStatus: (s) => s < 500 }
                      );
                      if (status === 202) message.info(data.message || '已提交人工确认');
                      else message.success('发布成功');
                      load();
                    } catch (e: any) {
                      message.error(e.message);
                      load();
                    }
                  },
                });
              }}
            >
              一键发布
            </Button>
          )
        }
      >
        <Table
          rowKey="id"
          dataSource={pubs}
          columns={[
            { title: '职位', dataIndex: ['job', 'title'] },
            { title: '渠道', dataIndex: ['channel', 'name'] },
            {
              title: '状态',
              dataIndex: 'status',
              render: (s) => <Tag color={s === 'PUBLISHED' ? 'green' : s === 'FAILED' ? 'red' : 'default'}>{s}</Tag>,
            },
            { title: '外部ID', dataIndex: 'externalRef' },
            { title: '结果', dataIndex: 'resultMsg', ellipsis: true },
            {
              title: '操作',
              render: (_, row) =>
                row.status === 'PUBLISHED' && (
                  <Button
                    type="link"
                    onClick={async () => {
                      await api.post(`/channels/publishes/${row.id}/status`, { status: 'PAUSED' });
                      load();
                    }}
                  >
                    暂停
                  </Button>
                ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
