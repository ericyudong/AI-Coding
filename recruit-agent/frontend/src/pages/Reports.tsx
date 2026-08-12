import { useEffect, useState } from 'react';
import { Card, Col, Row, Table, Button, message, Space, Tabs, Statistic } from 'antd';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import api from '../api';

export default function ReportsPage() {
  const [funnel, setFunnel] = useState<any[]>([]);
  const [channels, setChannels] = useState<any[]>([]);
  const [overview, setOverview] = useState<any[]>([]);
  const [cycle, setCycle] = useState<any>(null);
  const [reasons, setReasons] = useState<any>(null);
  const [efficiency, setEfficiency] = useState<any>(null);
  const [channelQuality, setChannelQuality] = useState<any[]>([]);
  const [interviewQuality, setInterviewQuality] = useState<any>(null);
  const [hireQuality, setHireQuality] = useState<any>(null);

  useEffect(() => {
    (async () => {
      try {
        const [f, c, o, cy, r, ef, cq, iq, hq] = await Promise.all([
          api.get('/reports/funnel'),
          api.get('/reports/channels'),
          api.get('/reports/overview'),
          api.get('/reports/cycle'),
          api.get('/reports/reasons'),
          api.get('/reports/efficiency'),
          api.get('/reports/channel-quality'),
          api.get('/reports/interview-quality'),
          api.get('/reports/hire-quality'),
        ]);
        setFunnel(f.data.stages);
        setChannels(c.data);
        setOverview(o.data.requests);
        setCycle(cy.data);
        setReasons(r.data);
        setEfficiency(ef.data);
        setChannelQuality(cq.data);
        setInterviewQuality(iq.data);
        setHireQuality(hq.data);
      } catch (e: any) {
        message.error(e.message);
      }
    })();
  }, []);

  return (
    <Tabs
      items={[
        {
          key: 'basic',
          label: '基础看板',
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              <Row gutter={16}>
                <Col span={14}>
                  <Card title="招聘漏斗（按应聘记录计数）">
                    <div style={{ height: 280 }}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={funnel}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="label" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="count" fill="#1f6b4a" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                </Col>
                <Col span={10}>
                  <Card title="招聘周期（天）">
                    <p>平均总周期：{cycle?.average?.totalDays ?? '-'}</p>
                    <p>进入→初面：{cycle?.average?.enterToInterview ?? '-'}</p>
                    <p>初面→Offer：{cycle?.average?.interviewToOffer ?? '-'}</p>
                    <p>Offer→入职：{cycle?.average?.offerToHire ?? '-'}</p>
                  </Card>
                </Col>
              </Row>
              <Card title="需求完成情况">
                <Table
                  rowKey="id"
                  dataSource={overview}
                  pagination={false}
                  columns={[
                    { title: '需求', dataIndex: 'name' },
                    { title: '部门', dataIndex: 'orgName' },
                    { title: '需求人数', dataIndex: 'headcount' },
                    { title: '已入职', dataIndex: 'hiredCount' },
                    { title: '待入职', dataIndex: 'pendingOnboard' },
                    { title: '缺口', dataIndex: 'gap' },
                    { title: '负责人', dataIndex: 'hrOwner' },
                    { title: '状态', dataIndex: 'status' },
                  ]}
                />
              </Card>
              <Row gutter={16}>
                <Col span={12}>
                  <Card title="渠道统计">
                    <Table
                      rowKey="source"
                      dataSource={channels}
                      pagination={false}
                      columns={[
                        { title: '来源', dataIndex: 'source' },
                        { title: '简历', dataIndex: 'resumes' },
                        { title: '面试', dataIndex: 'interviews' },
                        { title: 'Offer', dataIndex: 'offers' },
                        { title: '入职', dataIndex: 'hired' },
                      ]}
                    />
                  </Card>
                </Col>
                <Col span={12}>
                  <Card
                    title="原因分析"
                    extra={
                      <Button
                        onClick={async () => {
                          const { data } = await api.get('/reports/export');
                          const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = 'recruit-export.json';
                          a.click();
                          message.success('已导出');
                        }}
                      >
                        导出明细
                      </Button>
                    }
                  >
                    <p>筛选/面试淘汰：{(reasons?.reject || []).map((x: any) => `${x.reason}(${x.count})`).join('、') || '-'}</p>
                    <p>Offer拒绝：{(reasons?.offerDecline || []).map((x: any) => `${x.reason}(${x.count})`).join('、') || '-'}</p>
                    <p>待入职放弃：{(reasons?.abandon || []).map((x: any) => `${x.reason}(${x.count})`).join('、') || '-'}</p>
                  </Card>
                </Col>
              </Row>
            </Space>
          ),
        },
        {
          key: 'advanced',
          label: '进阶分析',
          children: (
            <Space direction="vertical" style={{ width: '100%' }} size={16}>
              <Row gutter={16}>
                <Col span={8}>
                  <Card>
                    <Statistic title="SLA达成率%" value={efficiency?.slaAttainment ?? '-'} />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card>
                    <Statistic title="评价及时率%" value={interviewQuality?.timelyRate ?? '-'} />
                  </Card>
                </Col>
                <Col span={8}>
                  <Card>
                    <Statistic title="未解决预警" value={efficiency?.openAlerts ?? 0} />
                  </Card>
                </Col>
              </Row>
              <Card title="招聘效能（按负责人）">
                <Table
                  rowKey="name"
                  dataSource={efficiency?.byOwner || []}
                  pagination={false}
                  columns={[
                    { title: '招聘负责人', dataIndex: 'name' },
                    { title: '应聘数', dataIndex: 'count' },
                    { title: '平均周期(天)', dataIndex: 'avgDays' },
                  ]}
                />
              </Card>
              <Card title="渠道质量">
                <Table
                  rowKey="source"
                  dataSource={channelQuality}
                  pagination={false}
                  columns={[
                    { title: '来源', dataIndex: 'source' },
                    { title: '简历', dataIndex: 'resumes' },
                    { title: '有效率%', dataIndex: 'validRate' },
                    { title: '面试率%', dataIndex: 'interviewRate' },
                    { title: 'Offer率%', dataIndex: 'offerRate' },
                    { title: '入职率%', dataIndex: 'hireRate' },
                  ]}
                />
              </Card>
              <Row gutter={16}>
                <Col span={12}>
                  <Card title="面试质量">
                    <p>平均评分：{interviewQuality?.avgScore ?? '-'}</p>
                    <p>评价分歧场次：{interviewQuality?.disagreementCount ?? 0}</p>
                    <p>已提交评价数：{interviewQuality?.evaluationCount ?? 0}</p>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="招聘质量回溯">
                    <p>已入职样本：{hireQuality?.hiredCount ?? 0}</p>
                    <p>按渠道：{JSON.stringify(hireQuality?.bySource || {})}</p>
                    <p>按岗位：{JSON.stringify(hireQuality?.byJob || {})}</p>
                    <p>质量记录数：{hireQuality?.records?.length ?? 0}</p>
                  </Card>
                </Col>
              </Row>
            </Space>
          ),
        },
      ]}
    />
  );
}
