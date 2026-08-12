import { useEffect, useState } from 'react';
import { Button, Card, Modal, Select, Space, Table, Tag, message, Form, Input } from 'antd';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function TalentPoolPage() {
  const [list, setList] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const { user } = useAuth();

  const load = async () => {
    const [t, j] = await Promise.all([api.get('/talent-pool'), api.get('/jobs')]);
    setList(t.data);
    setJobs(j.data.filter((x: any) => x.status === 'OPEN'));
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Card title="人才库">
      <Table
        rowKey="id"
        dataSource={list}
        columns={[
          { title: '姓名', dataIndex: 'name' },
          { title: '手机', dataIndex: 'phone' },
          { title: '学历', dataIndex: 'education' },
          { title: '城市', dataIndex: 'city' },
          { title: '分类', dataIndex: 'poolCategory' },
          { title: '储备说明', dataIndex: 'poolRemark' },
          {
            title: '标签',
            dataIndex: 'tags',
            render: (t) => (t ? String(t).split(',').map((x: string) => <Tag key={x}>{x}</Tag>) : '-'),
          },
          {
            title: '操作',
            render: (_, row) =>
              canRole(user!.role, 'HR', 'RECRUIT_LEAD') && (
                <Space>
                  <Button
                    type="link"
                    onClick={() => {
                      Modal.confirm({
                        title: '重新应聘',
                        content: (
                          <Select
                            style={{ width: '100%', marginTop: 12 }}
                            options={jobs.map((j) => ({ value: j.id, label: j.title }))}
                            onChange={(v) => ((Modal as any)._jobId = v)}
                          />
                        ),
                        onOk: async () => {
                          await api.post(`/talent-pool/${row.id}/reapply`, { jobId: (Modal as any)._jobId });
                          message.success('已生成新应聘记录');
                        },
                      });
                    }}
                  >
                    重新应聘
                  </Button>
                  <Button
                    type="link"
                    onClick={() => {
                      Modal.confirm({
                        title: '完善储备信息',
                        content: (
                          <Form layout="vertical" id="poolForm" style={{ marginTop: 12 }}>
                            <Form.Item label="分类">
                              <Input id="poolCategory" defaultValue={row.poolCategory || ''} />
                            </Form.Item>
                            <Form.Item label="适合岗位">
                              <Input id="poolSuitable" defaultValue={row.poolSuitable || ''} />
                            </Form.Item>
                            <Form.Item label="说明">
                              <Input.TextArea id="poolRemark" defaultValue={row.poolRemark || ''} rows={2} />
                            </Form.Item>
                          </Form>
                        ),
                        onOk: async () => {
                          await api.post(`/talent-pool/${row.id}/add`, {
                            poolCategory: (document.getElementById('poolCategory') as HTMLInputElement).value,
                            poolSuitable: (document.getElementById('poolSuitable') as HTMLInputElement).value,
                            poolRemark: (document.getElementById('poolRemark') as HTMLTextAreaElement).value,
                          });
                          message.success('已更新');
                          load();
                        },
                      });
                    }}
                  >
                    编辑
                  </Button>
                </Space>
              ),
          },
        ]}
      />
    </Card>
  );
}
