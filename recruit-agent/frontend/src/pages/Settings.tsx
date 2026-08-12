import { useEffect, useState } from 'react';
import { Card, Tabs, Table, Tag, Button, Form, Input, Modal, Select, Switch, message, Space } from 'antd';
import dayjs from 'dayjs';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

export default function SettingsPage() {
  const [dicts, setDicts] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [templates, setTemplates] = useState<any[]>([]);
  const [roles, setRoles] = useState<any[]>([]);
  const [orgs, setOrgs] = useState<any[]>([]);
  const { user } = useAuth();

  const load = async () => {
    const [d, t, r, o] = await Promise.all([
      api.get('/config/dicts'),
      api.get('/config/templates'),
      api.get('/config/roles'),
      api.get('/config/orgs'),
    ]);
    setDicts(d.data);
    setTemplates(t.data);
    setRoles(r.data);
    setOrgs(o.data);
    if (canRole(user!.role, 'ADMIN', 'RECRUIT_LEAD')) {
      setUsers((await api.get('/config/users')).data);
    }
    if (user!.role === 'ADMIN') {
      setLogs((await api.get('/config/audit-logs')).data);
    }
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  return (
    <Card title="系统设置">
      <Tabs
        items={[
          {
            key: 'dicts',
            label: '基础字典',
            children: (
              <>
                {canRole(user!.role, 'ADMIN') && (
                  <Button
                    style={{ marginBottom: 12 }}
                    type="primary"
                    onClick={() => {
                      Modal.confirm({
                        title: '新增字典',
                        content: (
                          <Form layout="vertical" id="dictForm" style={{ marginTop: 12 }}>
                            <Form.Item label="类型"><Input id="dictType" /></Form.Item>
                            <Form.Item label="编码"><Input id="dictCode" /></Form.Item>
                            <Form.Item label="名称"><Input id="dictLabel" /></Form.Item>
                          </Form>
                        ),
                        onOk: async () => {
                          await api.post('/config/dicts', {
                            type: (document.getElementById('dictType') as HTMLInputElement).value,
                            code: (document.getElementById('dictCode') as HTMLInputElement).value,
                            label: (document.getElementById('dictLabel') as HTMLInputElement).value,
                          });
                          message.success('已新增');
                          load();
                        },
                      });
                    }}
                  >
                    新增
                  </Button>
                )}
                <Table
                  rowKey="id"
                  dataSource={dicts}
                  columns={[
                    { title: '类型', dataIndex: 'type' },
                    { title: '编码', dataIndex: 'code' },
                    { title: '名称', dataIndex: 'label' },
                    { title: '启用', dataIndex: 'active', render: (v) => (v ? '是' : '否') },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'templates',
            label: '模板管理',
            children: (
              <Table
                rowKey="id"
                dataSource={templates}
                columns={[
                  { title: '类型', dataIndex: 'type' },
                  { title: '名称', dataIndex: 'name' },
                  { title: '启用', dataIndex: 'active', render: (v) => (v ? <Tag color="green">启用</Tag> : <Tag>停用</Tag>) },
                  {
                    title: '内容预览',
                    dataIndex: 'content',
                    ellipsis: true,
                  },
                ]}
              />
            ),
          },
          {
            key: 'users',
            label: '账号与角色',
            children: canRole(user!.role, 'ADMIN', 'RECRUIT_LEAD') ? (
              <>
                {user!.role === 'ADMIN' && (
                  <Button
                    type="primary"
                    style={{ marginBottom: 12, background: '#1f6b4a' }}
                    onClick={() => {
                      let formData: any = { role: 'HR', dataScope: 'SELF' };
                      Modal.confirm({
                        title: '创建账号',
                        width: 480,
                        content: (
                          <Form
                            layout="vertical"
                            style={{ marginTop: 12 }}
                            initialValues={formData}
                            onValuesChange={(_, all) => {
                              formData = all;
                            }}
                          >
                            <Form.Item name="username" label="用户名" required><Input /></Form.Item>
                            <Form.Item name="password" label="密码" required><Input.Password /></Form.Item>
                            <Form.Item name="name" label="姓名" required><Input /></Form.Item>
                            <Form.Item name="role" label="角色" required>
                              <Select options={roles} fieldNames={{ value: 'value', label: 'label' }} />
                            </Form.Item>
                            <Form.Item name="orgId" label="组织">
                              <Select options={orgs.map((o) => ({ value: o.id, label: o.name }))} />
                            </Form.Item>
                            <Form.Item name="dataScope" label="数据范围">
                              <Select
                                options={[
                                  { value: 'ALL', label: '全公司' },
                                  { value: 'DEPT', label: '本部门' },
                                  { value: 'SELF', label: '本人负责' },
                                ]}
                              />
                            </Form.Item>
                          </Form>
                        ),
                        onOk: async () => {
                          // fallback simple create via prompt fields if form values empty - use defaults
                          const username = (document.querySelector('#username') as HTMLInputElement)?.value;
                          await api.post('/config/users', {
                            username: formData.username || username,
                            password: formData.password || '123456',
                            name: formData.name || formData.username,
                            role: formData.role || 'HR',
                            orgId: formData.orgId,
                            dataScope: formData.dataScope || 'SELF',
                          });
                          message.success('账号已创建');
                          load();
                        },
                      });
                    }}
                  >
                    新建账号
                  </Button>
                )}
                <Table
                  rowKey="id"
                  dataSource={users}
                  columns={[
                    { title: '用户名', dataIndex: 'username' },
                    { title: '姓名', dataIndex: 'name' },
                    { title: '角色', dataIndex: 'roleLabel' },
                    { title: '组织', dataIndex: 'orgName' },
                    { title: '数据范围', dataIndex: 'dataScope' },
                    {
                      title: '状态',
                      dataIndex: 'active',
                      render: (v, row) =>
                        user!.role === 'ADMIN' ? (
                          <Switch
                            checked={v}
                            onChange={async (checked) => {
                              await api.put(`/config/users/${row.id}`, { active: checked });
                              load();
                            }}
                          />
                        ) : v ? (
                          '启用'
                        ) : (
                          '停用'
                        ),
                    },
                  ]}
                />
              </>
            ) : (
              <p>无权限查看账号列表</p>
            ),
          },
          {
            key: 'logs',
            label: '操作日志',
            children:
              user!.role === 'ADMIN' ? (
                <Table
                  rowKey="id"
                  dataSource={logs}
                  columns={[
                    {
                      title: '时间',
                      dataIndex: 'createdAt',
                      render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
                      width: 170,
                    },
                    { title: '操作人', dataIndex: 'userName', width: 100 },
                    { title: '动作', dataIndex: 'action' },
                    { title: '对象', dataIndex: 'objectType', width: 120 },
                    { title: '对象ID', dataIndex: 'objectId', ellipsis: true },
                    { title: '原因', dataIndex: 'reason', ellipsis: true },
                  ]}
                />
              ) : (
                <p>仅系统管理员可查看全量审计日志</p>
              ),
          },
        ]}
      />
    </Card>
  );
}
