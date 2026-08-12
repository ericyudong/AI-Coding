import { useEffect, useState } from 'react';
import {
  Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, DatePicker, message, Popconfirm, Descriptions,
} from 'antd';
import dayjs from 'dayjs';
import api from '../api';
import { REQUEST_STATUS, canRole } from '../constants';
import { useAuth } from '../auth';

export default function RequestsPage() {
  const [list, setList] = useState<any[]>([]);
  const [orgs, setOrgs] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<any>(null);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [r, o] = await Promise.all([api.get('/requests'), api.get('/config/orgs')]);
    setList(r.data);
    setOrgs(o.data);
    try {
      const u = await api.get('/config/users');
      setUsers(u.data);
    } catch {
      setUsers([]);
    }
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  const submit = async (values: any, doSubmit: boolean) => {
    try {
      await api.post('/requests', {
        ...values,
        expectDate: values.expectDate.format('YYYY-MM-DD'),
        submit: doSubmit,
      });
      message.success(doSubmit ? '已提交审批' : '草稿已保存');
      setOpen(false);
      form.resetFields();
      load();
    } catch (e: any) {
      message.error(e.message);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card
        title="招聘需求"
        extra={
          canRole(user!.role, 'HR', 'DEPT_HEAD', 'RECRUIT_LEAD') && (
            <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => setOpen(true)}>
              新建需求
            </Button>
          )
        }
      >
        <Table
          rowKey="id"
          dataSource={list}
          columns={[
            { title: '需求名称', dataIndex: 'name' },
            { title: '部门', dataIndex: ['org', 'name'] },
            { title: '岗位', dataIndex: 'positionTitle' },
            { title: '人数', dataIndex: 'headcount', width: 70 },
            { title: '已入职', dataIndex: 'hiredCount', width: 70 },
            {
              title: '期望到岗',
              dataIndex: 'expectDate',
              render: (v) => dayjs(v).format('YYYY-MM-DD'),
            },
            {
              title: '状态',
              dataIndex: 'status',
              render: (s) => <Tag color={REQUEST_STATUS[s]?.color}>{REQUEST_STATUS[s]?.text || s}</Tag>,
            },
            { title: '招聘HR', dataIndex: ['hrOwner', 'name'] },
            {
              title: '操作',
              render: (_, row) => (
                <Space>
                  <Button type="link" onClick={async () => setDetail((await api.get(`/requests/${row.id}`)).data)}>
                    详情
                  </Button>
                  {row.status === 'PENDING' && canRole(user!.role, 'RECRUIT_LEAD') && (
                    <>
                      <Button
                        type="link"
                        onClick={async () => {
                          await api.post(`/requests/${row.id}/approve`, { action: 'approve', hrOwnerId: users.find((u) => u.role === 'HR')?.id });
                          message.success('已通过');
                          load();
                        }}
                      >
                        通过
                      </Button>
                      <Popconfirm
                        title="驳回原因"
                        description={<Input.TextArea id="rejectReason" rows={2} />}
                        onConfirm={async () => {
                          const el = document.getElementById('rejectReason') as HTMLTextAreaElement;
                          await api.post(`/requests/${row.id}/approve`, { action: 'reject', comment: el?.value || '不符合编制' });
                          message.success('已驳回');
                          load();
                        }}
                      >
                        <Button type="link" danger>
                          驳回
                        </Button>
                      </Popconfirm>
                    </>
                  )}
                  {['APPROVED', 'RECRUITING'].includes(row.status) && canRole(user!.role, 'RECRUIT_LEAD') && (
                    <Button
                      type="link"
                      onClick={() => {
                        Modal.confirm({
                          title: '分配招聘HR',
                          content: (
                            <Select
                              style={{ width: '100%', marginTop: 12 }}
                              options={users.filter((u) => u.role === 'HR' || u.role === 'RECRUIT_LEAD').map((u) => ({ value: u.id, label: u.name }))}
                              onChange={(v) => ((Modal as any)._hr = v)}
                            />
                          ),
                          onOk: async () => {
                            await api.post(`/requests/${row.id}/assign`, { hrOwnerId: (Modal as any)._hr });
                            message.success('已分配');
                            load();
                          },
                        });
                      }}
                    >
                      分配HR
                    </Button>
                  )}
                  {row.status === 'DRAFT' && (
                    <Popconfirm title="确认删除草稿？" onConfirm={async () => { await api.delete(`/requests/${row.id}`); load(); }}>
                      <Button type="link" danger>
                        删除
                      </Button>
                    </Popconfirm>
                  )}
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal title="新建招聘需求" open={open} onCancel={() => setOpen(false)} footer={null} width={640} destroyOnClose>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ headcount: 1, reason: '新增编制', expectDate: dayjs().add(30, 'day') }}
          onFinish={(v) => submit(v, true)}
        >
          <Form.Item name="name" label="需求名称">
            <Input placeholder="默认：部门+岗位+人数" />
          </Form.Item>
          <Form.Item name="orgId" label="需求部门" rules={[{ required: true }]}>
            <Select options={orgs.map((o) => ({ value: o.id, label: o.name }))} />
          </Form.Item>
          <Form.Item name="positionTitle" label="岗位" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space style={{ display: 'flex' }} size={16}>
            <Form.Item name="headcount" label="需求人数" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="reason" label="招聘原因" rules={[{ required: true }]}>
              <Select
                options={[
                  { value: '新增编制', label: '新增编制' },
                  { value: '人员替补', label: '人员替补' },
                  { value: '业务项目', label: '业务项目' },
                  { value: '其他', label: '其他' },
                ]}
                style={{ width: 160 }}
              />
            </Form.Item>
            <Form.Item name="expectDate" label="期望到岗" rules={[{ required: true }]}>
              <DatePicker />
            </Form.Item>
          </Space>
          <Form.Item name="workLocation" label="工作地点" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space>
            <Form.Item name="salaryMin" label="薪资最低(K)">
              <InputNumber style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="salaryMax" label="薪资最高(K)">
              <InputNumber style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item name="description" label="需求说明">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Space>
            <Button onClick={() => form.validateFields().then((v) => submit(v, false))}>保存草稿</Button>
            <Button type="primary" htmlType="submit" style={{ background: '#1f6b4a' }}>
              提交审批
            </Button>
          </Space>
        </Form>
      </Modal>

      <Modal title="需求详情" open={!!detail} onCancel={() => setDetail(null)} footer={null} width={720}>
        {detail && (
          <Descriptions column={2} bordered size="small">
            <Descriptions.Item label="名称">{detail.name}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={REQUEST_STATUS[detail.status]?.color}>{REQUEST_STATUS[detail.status]?.text}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="部门">{detail.org?.name}</Descriptions.Item>
            <Descriptions.Item label="岗位">{detail.positionTitle}</Descriptions.Item>
            <Descriptions.Item label="人数">{detail.headcount}</Descriptions.Item>
            <Descriptions.Item label="已入职">{detail.hiredCount}</Descriptions.Item>
            <Descriptions.Item label="到岗日期">{dayjs(detail.expectDate).format('YYYY-MM-DD')}</Descriptions.Item>
            <Descriptions.Item label="地点">{detail.workLocation}</Descriptions.Item>
            <Descriptions.Item label="招聘HR">{detail.hrOwner?.name || '-'}</Descriptions.Item>
            <Descriptions.Item label="部门负责人">{detail.deptHead?.name || '-'}</Descriptions.Item>
            <Descriptions.Item label="说明" span={2}>{detail.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="关联职位" span={2}>
              {(detail.jobs || []).map((j: any) => j.title).join('、') || '暂无'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </Space>
  );
}
