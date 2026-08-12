import { useEffect, useState } from 'react';
import { Button, Card, DatePicker, Form, Input, Modal, Select, Space, Table, Tag, message, Checkbox } from 'antd';
import dayjs from 'dayjs';
import api from '../api';
import { ONBOARD_STATUS, canRole } from '../constants';
import { useAuth } from '../auth';

export default function OnboardingPage() {
  const [list, setList] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const { user } = useAuth();

  const load = async () => {
    const { data } = await api.get('/onboarding');
    setList(data);
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Card title="待入职与入职归档">
      <Table
        rowKey="id"
        dataSource={list}
        columns={[
          { title: '候选人', dataIndex: ['application', 'candidate', 'name'] },
          { title: '职位', dataIndex: ['application', 'job', 'title'] },
          { title: '部门', dataIndex: ['application', 'job', 'org', 'name'] },
          {
            title: '拟入职',
            dataIndex: 'expectedDate',
            render: (v) => dayjs(v).format('YYYY-MM-DD'),
          },
          {
            title: '状态',
            dataIndex: 'status',
            render: (s) => <Tag color={ONBOARD_STATUS[s]?.color}>{ONBOARD_STATUS[s]?.text || s}</Tag>,
          },
          { title: '员工编号', dataIndex: 'employeeNo' },
          {
            title: '操作',
            render: (_, row) => (
              <Space>
                <Button
                  type="link"
                  onClick={async () => {
                    const { data } = await api.get(`/onboarding/${row.id}`);
                    setDetail(data);
                  }}
                >
                  详情
                </Button>
                {canRole(user!.role, 'HR_OPS', 'HR') && !['HIRED', 'ABANDONED'].includes(row.status) && (
                  <Button
                    type="link"
                    onClick={async () => {
                      await api.post(`/onboarding/${row.id}/confirm`, {
                        confirmedDate: dayjs().format('YYYY-MM-DD'),
                        contactPerson: user?.name,
                      });
                      message.success('已确认');
                      load();
                    }}
                  >
                    确认
                  </Button>
                )}
                {canRole(user!.role, 'HR_OPS') && !['HIRED', 'ABANDONED'].includes(row.status) && (
                  <Button
                    type="link"
                    onClick={() => {
                      Modal.confirm({
                        title: '确认入职',
                        content: (
                          <Form layout="vertical" style={{ marginTop: 12 }}>
                            <Form.Item label="实际入职日期" required>
                              <DatePicker id="hireDate" defaultValue={dayjs()} />
                            </Form.Item>
                            <Form.Item label="员工编号">
                              <Input id="empNo" placeholder="不填则自动生成" />
                            </Form.Item>
                          </Form>
                        ),
                        onOk: async () => {
                          const dateEl = document.getElementById('hireDate') as any;
                          const noEl = document.getElementById('empNo') as HTMLInputElement;
                          const { data } = await api.post(`/onboarding/${row.id}/hire`, {
                            actualDate: dayjs().format('YYYY-MM-DD'),
                            employeeNo: noEl?.value || undefined,
                          });
                          message.success(`入职成功：${data.employeeArchive.employeeNo}`);
                          if (data.tips) message.info(data.tips);
                          load();
                        },
                      });
                    }}
                  >
                    确认入职
                  </Button>
                )}
              </Space>
            ),
          },
        ]}
      />

      <Modal title="待入职详情" open={!!detail} onCancel={() => setDetail(null)} footer={null} width={720}>
        {detail && (
          <>
            <p>
              {detail.application.candidate.name} · {detail.application.job.title} ·{' '}
              <Tag>{ONBOARD_STATUS[detail.status]?.text}</Tag>
            </p>
            <Card size="small" title="材料清单" style={{ marginBottom: 12 }}>
              {(detail.materials || []).map((m: any, idx: number) => (
                <div key={idx} style={{ marginBottom: 8 }}>
                  <Checkbox
                    checked={m.status === 'RECEIVED'}
                    onChange={async (e) => {
                      const materials = [...detail.materials];
                      materials[idx] = { ...m, status: e.target.checked ? 'RECEIVED' : 'PENDING' };
                      await api.put(`/onboarding/${detail.id}/materials`, { materials });
                      setDetail({ ...detail, materials });
                    }}
                  >
                    {m.name}（{m.status}）
                  </Checkbox>
                </div>
              ))}
            </Card>
            <Space>
              <Button
                onClick={() => {
                  Modal.confirm({
                    title: '延期入职',
                    content: <Input.TextArea id="delayReason" placeholder="原因" rows={2} />,
                    onOk: async () => {
                      const el = document.getElementById('delayReason') as HTMLTextAreaElement;
                      await api.post(`/onboarding/${detail.id}/delay`, {
                        expectedDate: dayjs(detail.expectedDate).add(7, 'day').format('YYYY-MM-DD'),
                        reason: el?.value || '个人原因延期',
                      });
                      message.success('已延期');
                      setDetail(null);
                      load();
                    },
                  });
                }}
              >
                延期
              </Button>
              <Button
                danger
                onClick={async () => {
                  await api.post(`/onboarding/${detail.id}/abandon`, { reason: '接受其他Offer' });
                  message.success('已放弃入职');
                  setDetail(null);
                  load();
                }}
              >
                放弃入职
              </Button>
              <Button
                onClick={async () => {
                  const { data } = await api.get(`/onboarding/${detail.id}/archive-export`);
                  Modal.info({
                    title: '员工档案导出',
                    content: <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(data, null, 2)}</pre>,
                    width: 640,
                  });
                }}
              >
                导出员工档案
              </Button>
            </Space>
          </>
        )}
      </Modal>
    </Card>
  );
}
