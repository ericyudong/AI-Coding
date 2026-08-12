import { useEffect, useState } from 'react';
import {
  Button, Card, Form, Input, Modal, Select, Space, Table, Tag, message, Descriptions, Timeline, InputNumber,
} from 'antd';
import api from '../api';
import { APP_STATUS, canRole } from '../constants';
import { useAuth } from '../auth';

export default function CandidatesPage() {
  const [list, setList] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<any>(null);
  const [duplicates, setDuplicates] = useState<any[]>([]);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [c, j] = await Promise.all([api.get('/candidates'), api.get('/jobs')]);
    setList(c.data);
    setJobs(j.data.filter((x: any) => x.status !== 'CLOSED'));
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  const createCandidate = async (values: any, force = false) => {
    try {
      await api.post('/candidates', { ...values, forceCreate: force });
      message.success('候选人已创建');
      setOpen(false);
      setDuplicates([]);
      form.resetFields();
      load();
    } catch (e: any) {
      if (e.data?.duplicates) {
        setDuplicates(e.data.duplicates);
        message.warning('发现重复候选人，请确认');
      } else {
        message.error(e.message);
      }
    }
  };

  return (
    <Card
      title="候选人与简历"
      extra={
        canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
          <Space>
            <Button
              onClick={() => {
                Modal.confirm({
                  title: '批量导入（JSON行）',
                  content: (
                    <Input.TextArea
                      id="importRows"
                      rows={6}
                      placeholder='[{"name":"张三","phone":"138...","source":"招聘网站"}]'
                    />
                  ),
                  width: 560,
                  onOk: async () => {
                    const el = document.getElementById('importRows') as HTMLTextAreaElement;
                    const rows = JSON.parse(el.value || '[]');
                    const { data } = await api.post('/candidates/import', { rows });
                    message.success(`成功 ${data.success}，失败 ${data.failed.length}`);
                    load();
                  },
                });
              }}
            >
              批量导入
            </Button>
            <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => setOpen(true)}>
              新增候选人
            </Button>
          </Space>
        )
      }
    >
      <Table
        rowKey="id"
        dataSource={list}
        columns={[
          { title: '姓名', dataIndex: 'name' },
          { title: '手机', dataIndex: 'phone' },
          { title: '邮箱', dataIndex: 'email' },
          { title: '当前公司', dataIndex: 'currentCompany' },
          { title: '来源', dataIndex: 'source' },
          {
            title: '应聘职位',
            render: (_, row) =>
              (row.applications || []).map((a: any) => (
                <Tag key={a.id}>
                  {a.job?.title} · {APP_STATUS[a.status]?.text || a.status}
                </Tag>
              )),
          },
          {
            title: '人才库',
            dataIndex: 'inTalentPool',
            render: (v) => (v ? <Tag color="purple">是</Tag> : '-'),
          },
          {
            title: '操作',
            render: (_, row) => (
              <Button
                type="link"
                onClick={async () => {
                  const { data } = await api.get(`/candidates/${row.id}`);
                  setDetail(data);
                }}
              >
                全景详情
              </Button>
            ),
          },
        ]}
      />

      <Modal title="新增候选人" open={open} onCancel={() => { setOpen(false); setDuplicates([]); }} footer={null} width={640}>
        <Form form={form} layout="vertical" onFinish={(v) => createCandidate(v)} initialValues={{ source: '招聘网站' }}>
          <Form.Item name="name" label="姓名" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space style={{ display: 'flex' }} size={16}>
            <Form.Item name="phone" label="手机号">
              <Input />
            </Form.Item>
            <Form.Item name="email" label="邮箱">
              <Input />
            </Form.Item>
          </Space>
          <Form.Item name="source" label="简历来源" rules={[{ required: true }]}>
            <Select
              options={['招聘网站', '内推', '猎头', '人才库', '主动投递', '其他'].map((x) => ({ value: x, label: x }))}
            />
          </Form.Item>
          <Form.Item name="jobId" label="关联职位（创建应聘记录）">
            <Select allowClear options={jobs.map((j) => ({ value: j.id, label: j.title }))} />
          </Form.Item>
          <Space>
            <Form.Item name="currentCompany" label="当前公司">
              <Input />
            </Form.Item>
            <Form.Item name="currentTitle" label="当前职位">
              <Input />
            </Form.Item>
            <Form.Item name="yearsOfExp" label="工作年限">
              <InputNumber min={0} />
            </Form.Item>
          </Space>
          {duplicates.length > 0 && (
            <Card size="small" title="疑似重复" style={{ marginBottom: 12 }}>
              {duplicates.map((d) => (
                <div key={d.id}>
                  {d.name} / {d.phone} / {d.email}
                </div>
              ))}
              <Button style={{ marginTop: 8 }} onClick={() => form.validateFields().then((v) => createCandidate(v, true))}>
                仍要新建
              </Button>
            </Card>
          )}
          <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
            保存
          </Button>
        </Form>
      </Modal>

      <Modal title="候选人全景" open={!!detail} onCancel={() => setDetail(null)} footer={null} width={860}>
        {detail && (
          <>
            <Descriptions bordered size="small" column={2}>
              <Descriptions.Item label="姓名">{detail.name}</Descriptions.Item>
              <Descriptions.Item label="来源">{detail.source}</Descriptions.Item>
              <Descriptions.Item label="手机">{detail.phone}</Descriptions.Item>
              <Descriptions.Item label="邮箱">{detail.email}</Descriptions.Item>
              <Descriptions.Item label="公司">{detail.currentCompany}</Descriptions.Item>
              <Descriptions.Item label="职位">{detail.currentTitle}</Descriptions.Item>
            </Descriptions>
            <Card size="small" title="应聘记录" style={{ marginTop: 16 }}>
              {(detail.applications || []).map((a: any) => (
                <Card key={a.id} size="small" style={{ marginBottom: 8 }} title={`${a.job?.title} · ${APP_STATUS[a.status]?.text}`}>
                  <Timeline
                    items={(a.events || []).map((e: any) => ({
                      children: `${e.type} ${e.fromStatus || ''} → ${e.toStatus || ''} ${e.reason || e.detail || ''} · ${e.operatorName || ''}`,
                    }))}
                  />
                </Card>
              ))}
            </Card>
            {canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
              <Button
                style={{ marginTop: 8 }}
                onClick={() => {
                  Modal.confirm({
                    title: '关联新职位',
                    content: (
                      <Select
                        style={{ width: '100%', marginTop: 12 }}
                        options={jobs.map((j) => ({ value: j.id, label: j.title }))}
                        onChange={(v) => ((Modal as any)._jobId = v)}
                      />
                    ),
                    onOk: async () => {
                      await api.post(`/candidates/${detail.id}/link-job`, { jobId: (Modal as any)._jobId });
                      message.success('已生成独立应聘记录');
                      const { data } = await api.get(`/candidates/${detail.id}`);
                      setDetail(data);
                      load();
                    },
                  });
                }}
              >
                关联职位
              </Button>
            )}
          </>
        )}
      </Modal>
    </Card>
  );
}
