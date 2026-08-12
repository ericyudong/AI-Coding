import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Modal, Space, Table, Tag, message, Switch } from 'antd';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function FlowsPage() {
  const [list, setList] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [f, a, r] = await Promise.all([api.get('/flows'), api.get('/flows/alerts'), api.get('/flows/sla-rules')]);
    setList(f.data);
    setAlerts(a.data);
    setRules(r.data);
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card
        title="流程配置与 SLA"
        extra={
          <Space>
            {canRole(user!.role, 'ADMIN', 'RECRUIT_LEAD') && (
              <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => setOpen(true)}>
                新建流程模板
              </Button>
            )}
            <Button
              onClick={async () => {
                const { data } = await api.post('/flows/check-sla');
                message.info(`SLA巡检完成，新增预警 ${data.alerts} 条`);
                load();
              }}
            >
              执行SLA巡检
            </Button>
          </Space>
        }
      >
        <Table
          rowKey="id"
          dataSource={list}
          expandable={{
            expandedRowRender: (row) => (
              <Table
                size="small"
                pagination={false}
                rowKey="id"
                dataSource={row.nodes || []}
                columns={[
                  { title: '顺序', dataIndex: 'sort', width: 60 },
                  { title: '节点', dataIndex: 'name' },
                  { title: 'Key', dataIndex: 'key' },
                  { title: '类型', dataIndex: 'type' },
                  { title: '角色', dataIndex: 'role' },
                  { title: 'SLA(h)', dataIndex: 'slaHours' },
                  { title: '可跳过', dataIndex: 'skippable', render: (v) => (v ? '是' : '否') },
                ]}
              />
            ),
          }}
          columns={[
            { title: '流程名称', dataIndex: 'name' },
            { title: '说明', dataIndex: 'description' },
            { title: '节点数', render: (_, r) => r.nodes?.length || 0 },
            { title: '状态', dataIndex: 'active', render: (v) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>) },
          ]}
        />
      </Card>

      <Card title="SLA规则">
        <Table
          rowKey="id"
          dataSource={rules}
          pagination={false}
          columns={[
            { title: '名称', dataIndex: 'name' },
            { title: '范围', dataIndex: 'scope' },
            { title: '节点', dataIndex: 'nodeKey' },
            { title: '时限(h)', dataIndex: 'hours' },
            { title: '预警(h)', dataIndex: 'warnHours' },
            { title: '升级角色', dataIndex: 'escalateRole' },
          ]}
        />
      </Card>

      <Card title="预警列表">
        <Table
          rowKey="id"
          dataSource={alerts}
          columns={[
            { title: '类型', dataIndex: 'type' },
            { title: '标题', dataIndex: 'title' },
            { title: '级别', dataIndex: 'level' },
            { title: '详情', dataIndex: 'detail' },
            {
              title: '操作',
              render: (_, row) =>
                !row.resolved && (
                  <Button type="link" onClick={async () => { await api.post(`/flows/alerts/${row.id}/resolve`); load(); }}>
                    解决
                  </Button>
                ),
            },
          ]}
        />
      </Card>

      <Modal title="新建流程模板" open={open} onCancel={() => setOpen(false)} footer={null} width={720}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            name: '自定义流程',
            nodesJson: JSON.stringify(
              [
                { key: 'HR_SCREEN', name: 'HR筛选', type: 'SCREEN', role: 'HR', slaHours: 48 },
                { key: 'INTERVIEW', name: '面试', type: 'INTERVIEW', role: 'INTERVIEWER', slaHours: 120 },
                { key: 'OFFER', name: 'Offer', type: 'OFFER', role: 'HR', slaHours: 72 },
              ],
              null,
              2
            ),
          }}
          onFinish={async (v) => {
            try {
              const nodes = JSON.parse(v.nodesJson);
              await api.post('/flows', { name: v.name, description: v.description, nodes });
              message.success('流程模板已创建');
              setOpen(false);
              load();
            } catch (e: any) {
              message.error(e.message || '节点JSON无效');
            }
          }}
        >
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="说明">
            <Input />
          </Form.Item>
          <Form.Item name="nodesJson" label="节点JSON" rules={[{ required: true }]}>
            <Input.TextArea rows={12} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
            创建
          </Button>
        </Form>
      </Modal>
    </Space>
  );
}
