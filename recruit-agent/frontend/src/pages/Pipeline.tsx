import { useEffect, useState } from 'react';
import { Button, Card, Input, Modal, Select, Space, Table, Tag, message, Timeline, Form } from 'antd';
import { useSearchParams } from 'react-router-dom';
import api from '../api';
import { APP_STATUS, canRole } from '../constants';
import { useAuth } from '../auth';

export default function PipelinePage() {
  const [list, setList] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [params] = useSearchParams();
  const { user } = useAuth();
  const [jobId, setJobId] = useState<string | undefined>();
  const [status, setStatus] = useState<string | undefined>(params.get('status') || undefined);

  const load = async () => {
    const q: any = {};
    if (jobId) q.jobId = jobId;
    if (status) q.status = status;
    const [a, j] = await Promise.all([api.get('/applications', { params: q }), api.get('/jobs')]);
    setList(a.data);
    setJobs(j.data);
    try {
      setUsers((await api.get('/config/users')).data);
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, [jobId, status]);

  const openDetail = async (id: string) => {
    const { data } = await api.get(`/applications/${id}`);
    setSelected(data);
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Card title="招聘流程 / 应聘记录">
        <Space style={{ marginBottom: 16 }}>
          <Select
            allowClear
            placeholder="按职位筛选"
            style={{ width: 220 }}
            options={jobs.map((j) => ({ value: j.id, label: j.title }))}
            onChange={setJobId}
          />
          <Select
            allowClear
            placeholder="状态"
            style={{ width: 160 }}
            value={status}
            options={Object.entries(APP_STATUS).map(([value, v]) => ({ value, label: v.text }))}
            onChange={setStatus}
          />
        </Space>
        <Table
          rowKey="id"
          dataSource={list}
          columns={[
            { title: '候选人', dataIndex: ['candidate', 'name'] },
            { title: '职位', dataIndex: ['job', 'title'] },
            { title: '部门', dataIndex: ['job', 'org', 'name'] },
            {
              title: '状态',
              dataIndex: 'status',
              render: (s) => <Tag color={APP_STATUS[s]?.color}>{APP_STATUS[s]?.text || s}</Tag>,
            },
            { title: '筛选结果', dataIndex: 'screenResult' },
            {
              title: '操作',
              render: (_, row) => (
                <Space>
                  <Button type="link" onClick={() => openDetail(row.id)}>
                    详情/推进
                  </Button>
                </Space>
              ),
            },
          ]}
        />
      </Card>

      <Modal title="应聘记录详情" open={!!selected} onCancel={() => setSelected(null)} footer={null} width={900}>
        {selected && (
          <>
            <p>
              <b>{selected.candidate.name}</b> · {selected.job.title} ·{' '}
              <Tag color={APP_STATUS[selected.status]?.color}>{APP_STATUS[selected.status]?.text}</Tag>
            </p>
            <Space wrap style={{ marginBottom: 16 }}>
              {selected.status === 'HR_SCREEN' && canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
                <>
                  <Button
                    type="primary"
                    style={{ background: '#1f6b4a' }}
                    onClick={async () => {
                      await api.post(`/applications/${selected.id}/screen`, { result: 'PASS' });
                      message.success('已通过筛选');
                      setSelected(null);
                      load();
                    }}
                  >
                    HR通过
                  </Button>
                  <Button
                    onClick={() => {
                      Modal.confirm({
                        title: '待定原因',
                        content: <Input.TextArea id="pendingReason" rows={2} />,
                        onOk: async () => {
                          const el = document.getElementById('pendingReason') as HTMLTextAreaElement;
                          await api.post(`/applications/${selected.id}/screen`, { result: 'PENDING', reason: el.value });
                          message.success('已标记待定');
                          openDetail(selected.id);
                        },
                      });
                    }}
                  >
                    待定
                  </Button>
                  <Button
                    danger
                    onClick={() => {
                      Modal.confirm({
                        title: '淘汰原因',
                        content: (
                          <Form layout="vertical" id="rejectForm">
                            <Form.Item label="原因" required>
                              <Select
                                id="rejectReason"
                                options={['不匹配', '经验不足', '薪资不符', '候选人放弃', '岗位关闭'].map((x) => ({
                                  value: x,
                                  label: x,
                                }))}
                                defaultValue="经验不足"
                              />
                            </Form.Item>
                          </Form>
                        ),
                        onOk: async () => {
                          await api.post(`/applications/${selected.id}/screen`, {
                            result: 'REJECT',
                            reason: '经验不足',
                            toPool: false,
                          });
                          message.success('已淘汰');
                          setSelected(null);
                          load();
                        },
                      });
                    }}
                  >
                    不通过
                  </Button>
                  <Button
                    onClick={() => {
                      Modal.confirm({
                        title: '转交用人部门',
                        content: (
                          <Select
                            style={{ width: '100%', marginTop: 12 }}
                            options={users.filter((u) => u.role === 'DEPT_HEAD').map((u) => ({ value: u.id, label: u.name }))}
                            onChange={(v) => ((Modal as any)._assignee = v)}
                          />
                        ),
                        onOk: async () => {
                          await api.post(`/applications/${selected.id}/transfer-dept`, {
                            assigneeId: (Modal as any)._assignee,
                            focusPoints: '请关注技术深度',
                          });
                          message.success('已转交');
                          setSelected(null);
                          load();
                        },
                      });
                    }}
                  >
                    转交部门
                  </Button>
                </>
              )}
              {selected.status === 'DEPT_SCREEN' && canRole(user!.role, 'DEPT_HEAD', 'RECRUIT_LEAD') && (
                <>
                  <Button
                    type="primary"
                    onClick={async () => {
                      await api.post(`/applications/${selected.id}/dept-feedback`, { result: 'PASS', comment: '匹配，建议面试' });
                      message.success('部门已通过');
                      setSelected(null);
                      load();
                    }}
                  >
                    部门通过
                  </Button>
                  <Button
                    danger
                    onClick={async () => {
                      await api.post(`/applications/${selected.id}/dept-feedback`, {
                        result: 'REJECT',
                        comment: '不匹配',
                        toPool: true,
                      });
                      message.success('已淘汰并入库');
                      setSelected(null);
                      load();
                    }}
                  >
                    不通过并入库
                  </Button>
                </>
              )}
              {!['HIRED', 'REJECTED', 'WITHDRAWN'].includes(selected.status) && canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
                <Button
                  danger
                  onClick={() => {
                    Modal.confirm({
                      title: '淘汰并可选入库',
                      content: <Input.TextArea id="rejectAll" placeholder="原因" rows={2} />,
                      onOk: async () => {
                        const el = document.getElementById('rejectAll') as HTMLTextAreaElement;
                        await api.post(`/applications/${selected.id}/reject`, {
                          reason: el?.value || '不匹配',
                          toPool: true,
                        });
                        message.success('已淘汰');
                        setSelected(null);
                        load();
                      },
                    });
                  }}
                >
                  淘汰/入人才库
                </Button>
              )}
            </Space>
            <Card size="small" title="流程时间轴">
              <Timeline
                items={(selected.events || []).map((e: any) => ({
                  children: `${e.createdAt?.slice(0, 19).replace('T', ' ')} · ${e.type} · ${e.fromStatus || ''}→${e.toStatus || ''} · ${e.reason || e.detail || ''} · ${e.operatorName || ''}`,
                }))}
              />
            </Card>
          </>
        )}
      </Modal>
    </Space>
  );
}
