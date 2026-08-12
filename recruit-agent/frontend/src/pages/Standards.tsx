import { useEffect, useState } from 'react';
import { Button, Card, Form, Input, InputNumber, Modal, Select, Space, Table, Tag, message, Tabs } from 'antd';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function StandardsPage() {
  const [list, setList] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [calibration, setCalibration] = useState<any>(null);
  const [flows, setFlows] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const { user } = useAuth();

  const load = async () => {
    const [s, m, c, f, j] = await Promise.all([
      api.get('/standards'),
      api.get('/standards/eval-models'),
      api.get('/standards/calibration'),
      api.get('/flows'),
      api.get('/jobs'),
    ]);
    setList(s.data);
    setModels(m.data);
    setCalibration(c.data);
    setFlows(f.data);
    setJobs(j.data);
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Card title="岗位标准与评价模型（二期）">
      <Tabs
        items={[
          {
            key: 'standards',
            label: '岗位招聘模板',
            children: (
              <>
                {canRole(user!.role, 'HR', 'RECRUIT_LEAD', 'ADMIN') && (
                  <Button type="primary" style={{ marginBottom: 12, background: '#1f6b4a' }} onClick={() => setOpen(true)}>
                    新建/升版标准
                  </Button>
                )}
                <Table
                  rowKey="id"
                  dataSource={list}
                  columns={[
                    { title: '编码', dataIndex: 'code' },
                    { title: '名称', dataIndex: 'name' },
                    { title: '岗位族', dataIndex: 'family' },
                    { title: '版本', dataIndex: 'version', render: (v, r) => <Tag color={r.isLatest ? 'green' : 'default'}>v{v}</Tag> },
                    { title: '硬性条件', dataIndex: 'hardCriteria', ellipsis: true },
                    {
                      title: '操作',
                      render: (_, row) => (
                        <Button
                          type="link"
                          onClick={() => {
                            Modal.confirm({
                              title: '应用到职位',
                              content: (
                                <Select
                                  style={{ width: '100%', marginTop: 12 }}
                                  options={jobs.map((j) => ({ value: j.id, label: j.title }))}
                                  onChange={(v) => ((Modal as any)._jobId = v)}
                                />
                              ),
                              onOk: async () => {
                                await api.post(`/standards/apply-to-job/${(Modal as any)._jobId}`, { standardId: row.id });
                                message.success('已应用（历史应聘仍可定位当时版本）');
                                load();
                              },
                            });
                          }}
                        >
                          应用到职位
                        </Button>
                      ),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'models',
            label: '评价模型',
            children: (
              <Table
                rowKey="id"
                dataSource={models}
                columns={[
                  { title: '名称', dataIndex: 'name' },
                  { title: '岗位族', dataIndex: 'jobFamily' },
                  { title: '及格线', dataIndex: 'passScore' },
                  { title: '版本', dataIndex: 'version' },
                  { title: '维度配置', dataIndex: 'dimensions', ellipsis: true },
                ]}
              />
            ),
          },
          {
            key: 'calibration',
            label: '标准校准',
            children: (
              <Table
                rowKey="name"
                dataSource={calibration?.interviewers || []}
                columns={[
                  { title: '面试官', dataIndex: 'name' },
                  { title: '评价数', dataIndex: 'count' },
                  { title: '平均分', dataIndex: 'avg' },
                ]}
                footer={() => `总评价数：${calibration?.totalEvaluations || 0}（用于校准岗位标准与权重）`}
              />
            ),
          },
        ]}
      />

      <Modal title="岗位标准" open={open} onCancel={() => setOpen(false)} footer={null} width={640}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{ code: 'FE-SENIOR', family: '工程-前端' }}
          onFinish={async (v) => {
            try {
              await api.post('/standards', {
                ...v,
                flowTemplateId: v.flowTemplateId,
                skills: (v.skills || '').split(',').filter(Boolean),
              });
              message.success('已保存（同编码自动升版）');
              setOpen(false);
              load();
            } catch (e: any) {
              message.error(e.message);
            }
          }}
        >
          <Form.Item name="code" label="编码" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="name" label="名称" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="family" label="岗位族">
            <Input />
          </Form.Item>
          <Form.Item name="jd" label="JD">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="requirements" label="任职条件">
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item name="skills" label="技能（逗号分隔）">
            <Input />
          </Form.Item>
          <Form.Item name="flowTemplateId" label="默认流程">
            <Select options={flows.map((f) => ({ value: f.id, label: f.name }))} allowClear />
          </Form.Item>
          <Button type="primary" htmlType="submit" block style={{ background: '#1f6b4a' }}>
            保存
          </Button>
        </Form>
      </Modal>
    </Card>
  );
}
