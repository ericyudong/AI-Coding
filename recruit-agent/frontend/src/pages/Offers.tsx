import { useEffect, useState } from 'react';
import { Button, Card, DatePicker, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message, Typography } from 'antd';
import dayjs from 'dayjs';
import api from '../api';
import { OFFER_STATUS, canRole } from '../constants';
import { useAuth } from '../auth';

export default function OffersPage() {
  const [list, setList] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [o, a] = await Promise.all([api.get('/offers'), api.get('/applications')]);
    setList(o.data);
    setApps(a.data.filter((x: any) => ['OFFER', 'INTERVIEW'].includes(x.status)));
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  const createOfferLink = async (offer: any) => {
    const { data } = await api.post('/links/create', {
      type: 'OFFER_CONFIRM',
      offerId: offer.id,
      applicationId: offer.applicationId,
      candidateId: offer.application?.candidate?.id,
      hours: 72,
    });
    Modal.info({
      title: '候选人Offer确认链接',
      content: <Typography.Paragraph copyable>{`${window.location.origin}${data.url}`}</Typography.Paragraph>,
    });
  };

  return (
    <Card
      title="Offer管理"
      extra={
        canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
          <Button type="primary" style={{ background: '#1f6b4a' }} onClick={() => setOpen(true)}>
            创建Offer
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
          { title: '版本', dataIndex: 'version', width: 70 },
          { title: '基本工资', dataIndex: 'baseSalary', render: (v) => (v == null ? '***' : v) },
          {
            title: '拟入职',
            dataIndex: 'expectedHireDate',
            render: (v) => dayjs(v).format('YYYY-MM-DD'),
          },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s) => <Tag color={OFFER_STATUS[s]?.color}>{OFFER_STATUS[s]?.text || s}</Tag>,
          },
          {
            title: '操作',
            render: (_, row) => (
              <Space wrap>
                <Button
                  type="link"
                  onClick={async () => {
                    const { data } = await api.get(`/offers/${row.id}/preview`);
                    Modal.info({
                      title: 'Offer预览',
                      width: 640,
                      content: <Typography.Paragraph copyable style={{ whiteSpace: 'pre-wrap' }}>{data.text}</Typography.Paragraph>,
                    });
                  }}
                >
                  预览
                </Button>
                {row.status === 'PENDING' && canRole(user!.role, 'OFFER_APPROVER', 'RECRUIT_LEAD') && (
                  <>
                    <Button
                      type="link"
                      onClick={async () => {
                        await api.post(`/offers/${row.id}/approve`, { action: 'approve' });
                        message.success('已通过');
                        load();
                      }}
                    >
                      审批通过
                    </Button>
                    <Button
                      type="link"
                      danger
                      onClick={async () => {
                        await api.post(`/offers/${row.id}/approve`, { action: 'reject', comment: '薪酬需调整' });
                        message.success('已驳回');
                        load();
                      }}
                    >
                      驳回
                    </Button>
                  </>
                )}
                {row.status === 'APPROVED' && canRole(user!.role, 'HR') && (
                  <>
                    <Button
                      type="link"
                      onClick={async () => {
                        await api.post(`/offers/${row.id}/send`, { validUntil: dayjs().add(7, 'day').toISOString() });
                        message.success('已记录发送');
                        load();
                      }}
                    >
                      记录发送
                    </Button>
                    <Button type="link" onClick={() => createOfferLink(row)}>
                      外链确认
                    </Button>
                    <Button
                      type="link"
                      onClick={async () => {
                        const { data } = await api.post(`/p2/offers/${row.id}/esign`);
                        message.info(data.message);
                      }}
                    >
                      电子签
                    </Button>
                  </>
                )}
                {['SENT', 'APPROVED'].includes(row.status) && canRole(user!.role, 'HR') && (
                  <>
                    <Button
                      type="link"
                      onClick={async () => {
                        await api.post(`/offers/${row.id}/result`, { result: 'ACCEPTED' });
                        message.success('已接受，自动创建待入职');
                        load();
                      }}
                    >
                      接受
                    </Button>
                    <Button
                      type="link"
                      danger
                      onClick={async () => {
                        await api.post(`/offers/${row.id}/result`, { result: 'DECLINED', declineReason: '薪酬' });
                        message.success('已记录拒绝');
                        load();
                      }}
                    >
                      拒绝
                    </Button>
                    <Button type="link" onClick={() => createOfferLink(row)}>
                      外链确认
                    </Button>
                  </>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal title="创建Offer" open={open} onCancel={() => setOpen(false)} footer={null} width={640}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ probationMonths: 3, expectedHireDate: dayjs().add(14, 'day') }}
          onFinish={async (values) => {
            try {
              await api.post('/offers', {
                ...values,
                expectedHireDate: values.expectedHireDate.format('YYYY-MM-DD'),
                validUntil: values.validUntil?.format('YYYY-MM-DD'),
                submit: true,
                force: true,
              });
              message.success('Offer已提交审批');
              setOpen(false);
              form.resetFields();
              load();
            } catch (e: any) {
              message.error(e.message);
            }
          }}
        >
          <Form.Item name="applicationId" label="应聘记录" rules={[{ required: true }]}>
            <Select
              options={apps.map((a) => ({ value: a.id, label: `${a.candidate.name} - ${a.job.title}` }))}
              onChange={(id) => {
                const a = apps.find((x) => x.id === id);
                if (a) form.setFieldsValue({ workLocation: a.job.workLocation });
              }}
            />
          </Form.Item>
          <Form.Item name="workLocation" label="工作地点" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Space>
            <Form.Item name="baseSalary" label="基本工资" rules={[{ required: true }]}>
              <InputNumber style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="performance" label="绩效">
              <InputNumber style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="bonus" label="奖金">
              <InputNumber style={{ width: 140 }} />
            </Form.Item>
          </Space>
          <Space>
            <Form.Item name="probationMonths" label="试用期(月)" rules={[{ required: true }]}>
              <InputNumber min={0} style={{ width: 120 }} />
            </Form.Item>
            <Form.Item name="probationSalary" label="试用薪资">
              <InputNumber style={{ width: 140 }} />
            </Form.Item>
            <Form.Item name="level" label="职级">
              <Select options={['P5', 'P6', 'P7'].map((x) => ({ value: x, label: x }))} style={{ width: 120 }} />
            </Form.Item>
          </Space>
          <Form.Item name="expectedHireDate" label="拟入职日期" rules={[{ required: true }]}>
            <DatePicker />
          </Form.Item>
          <Form.Item name="validUntil" label="有效期至">
            <DatePicker />
          </Form.Item>
          <Form.Item name="otherTerms" label="其他约定">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
            提交审批
          </Button>
        </Form>
      </Modal>
    </Card>
  );
}
