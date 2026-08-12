import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message, Typography } from 'antd';
import api from '../api';
import { JOB_STATUS, canRole } from '../constants';
import { useAuth } from '../auth';

export default function JobsPage() {
  const [list, setList] = useState<any[]>([]);
  const [requests, setRequests] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [edit, setEdit] = useState<any>(null);
  const [form] = Form.useForm();
  const [jdForm] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [j, r] = await Promise.all([api.get('/jobs'), api.get('/requests')]);
    setList(j.data);
    setRequests(r.data.filter((x: any) => ['APPROVED', 'RECRUITING'].includes(x.status)));
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Card
      title="职位管理"
      extra={
        canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
          <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => setOpen(true)}>
            从需求创建职位
          </Button>
        )
      }
    >
      <Table
        rowKey="id"
        dataSource={list}
        columns={[
          { title: '职位', dataIndex: 'title' },
          { title: '部门', dataIndex: ['org', 'name'] },
          { title: '人数', dataIndex: 'headcount', width: 70 },
          { title: '已入职', dataIndex: 'hiredCount', width: 70 },
          { title: '应聘数', dataIndex: ['_count', 'applications'], width: 80 },
          { title: '地点', dataIndex: 'workLocation' },
          { title: '负责人', dataIndex: ['hrOwner', 'name'] },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s) => <Tag color={JOB_STATUS[s]?.color}>{JOB_STATUS[s]?.text || s}</Tag>,
          },
          {
            title: '操作',
            render: (_, row) => (
              <Space>
                <Button
                  type="link"
                  onClick={() => {
                    setEdit(row);
                    jdForm.setFieldsValue(row);
                  }}
                >
                  维护JD
                </Button>
                {row.status !== 'OPEN' && (
                  <Button
                    type="link"
                    onClick={async () => {
                      const { data } = await api.post(`/jobs/${row.id}/publish`);
                      Modal.info({
                        title: '职位已发布，可复制对外文案',
                        content: <Typography.Paragraph copyable>{data.publishCopy}</Typography.Paragraph>,
                        width: 560,
                      });
                      load();
                    }}
                  >
                    发布
                  </Button>
                )}
                {row.status === 'OPEN' && (
                  <Button
                    type="link"
                    onClick={async () => {
                      await api.post(`/jobs/${row.id}/status`, { status: 'PAUSED' });
                      load();
                    }}
                  >
                    暂停
                  </Button>
                )}
                {row.status === 'PAUSED' && (
                  <Button
                    type="link"
                    onClick={async () => {
                      await api.post(`/jobs/${row.id}/status`, { status: 'OPEN' });
                      load();
                    }}
                  >
                    恢复
                  </Button>
                )}
                {row.status !== 'CLOSED' && (
                  <Button
                    type="link"
                    danger
                    onClick={() => {
                      Modal.confirm({
                        title: '关闭职位',
                        content: <Input.TextArea id="closeReason" placeholder="关闭原因" rows={2} />,
                        onOk: async () => {
                          const el = document.getElementById('closeReason') as HTMLTextAreaElement;
                          await api.post(`/jobs/${row.id}/status`, { status: 'CLOSED', reason: el?.value || '岗位关闭' });
                          load();
                        },
                      });
                    }}
                  >
                    关闭
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal title="创建职位" open={open} onCancel={() => setOpen(false)} footer={null}>
        <Form
          form={form}
          layout="vertical"
          onFinish={async (v) => {
            try {
              await api.post('/jobs', v);
              message.success('职位已创建');
              setOpen(false);
              form.resetFields();
              load();
            } catch (e: any) {
              message.error(e.message);
            }
          }}
        >
          <Form.Item name="requestId" label="招聘需求" rules={[{ required: true }]}>
            <Select
              options={requests.map((r) => ({ value: r.id, label: r.name }))}
              onChange={(id) => {
                const r = requests.find((x) => x.id === id);
                if (r) form.setFieldsValue({ title: r.positionTitle, headcount: r.headcount, workLocation: r.workLocation });
              }}
            />
          </Form.Item>
          <Form.Item name="title" label="职位名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="headcount" label="招聘人数" rules={[{ required: true }]}>
            <InputNumber min={1} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="workLocation" label="工作地点" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
            创建
          </Button>
        </Form>
      </Modal>

      <Modal
        title="维护JD与流程"
        open={!!edit}
        onCancel={() => setEdit(null)}
        onOk={() =>
          jdForm.validateFields().then(async (v) => {
            await api.put(`/jobs/${edit.id}`, v);
            message.success('已保存');
            setEdit(null);
            load();
          })
        }
        width={720}
      >
        <Form form={jdForm} layout="vertical">
          <Form.Item name="title" label="职位名称">
            <Input />
          </Form.Item>
          <Form.Item name="responsibilities" label="工作职责">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="requirements" label="任职要求">
            <Input.TextArea rows={4} />
          </Form.Item>
          <Form.Item name="bonuses" label="加分项">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="flowConfig" label="默认流程（逗号分隔）">
            <Input placeholder="HR_SCREEN,DEPT_SCREEN,FIRST_INTERVIEW,SECOND_INTERVIEW,OFFER" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
