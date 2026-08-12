import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, Select, Space, Table, Tag, message } from 'antd';
import dayjs from 'dayjs';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function MessagesPage() {
  const [list, setList] = useState<any[]>([]);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    setList((await api.get('/messages')).data);
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card title="发送消息（邮件/短信/企微模拟）">
        {canRole(user!.role, 'HR', 'RECRUIT_LEAD', 'ADMIN', 'HR_OPS') && (
          <Form
            form={form}
            layout="inline"
            style={{ marginBottom: 16, rowGap: 12 }}
            initialValues={{ channel: 'EMAIL' }}
            onFinish={async (v) => {
              try {
                await api.post('/messages/send', v);
                message.success('已发送');
                form.resetFields(['toAddr', 'subject', 'content']);
                load();
              } catch (e: any) {
                message.error(e.message);
                load();
              }
            }}
          >
            <Form.Item name="channel" label="渠道">
              <Select style={{ width: 120 }} options={['EMAIL', 'SMS', 'IM', 'INAPP'].map((x) => ({ value: x, label: x }))} />
            </Form.Item>
            <Form.Item name="toAddr" label="收件人" rules={[{ required: true }]}>
              <Input style={{ width: 180 }} />
            </Form.Item>
            <Form.Item name="subject" label="主题">
              <Input style={{ width: 160 }} />
            </Form.Item>
            <Form.Item name="content" label="内容" rules={[{ required: true }]}>
              <Input style={{ width: 260 }} />
            </Form.Item>
            <Button type="primary" htmlType="submit" style={{ background: '#1f6b4a' }}>
              发送
            </Button>
          </Form>
        )}
        <Table
          rowKey="id"
          dataSource={list}
          columns={[
            { title: '时间', dataIndex: 'createdAt', render: (v) => dayjs(v).format('MM-DD HH:mm'), width: 110 },
            { title: '渠道', dataIndex: 'channel', width: 80 },
            { title: '收件人', dataIndex: 'toAddr' },
            { title: '主题', dataIndex: 'subject' },
            { title: '内容', dataIndex: 'content', ellipsis: true },
            {
              title: '状态',
              dataIndex: 'status',
              render: (s) => <Tag color={s === 'SENT' ? 'green' : s === 'FAILED' ? 'red' : 'default'}>{s}</Tag>,
            },
            { title: '重试', dataIndex: 'retryCount', width: 60 },
            {
              title: '操作',
              render: (_, row) =>
                row.status === 'FAILED' && (
                  <Button
                    type="link"
                    onClick={async () => {
                      try {
                        await api.post(`/messages/${row.id}/retry`);
                        message.success('重试成功');
                      } catch (e: any) {
                        message.error(e.message);
                      }
                      load();
                    }}
                  >
                    重试
                  </Button>
                ),
            },
          ]}
        />
      </Card>
    </Space>
  );
}
