import { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Tabs,
  message,
  Typography,
  Alert,
  List,
  Spin,
  Divider,
  Descriptions,
} from 'antd';
import dayjs from 'dayjs';
import api from '../api';
import { canRole } from '../constants';
import { useAuth } from '../auth';

type ChatItem = { role: 'user' | 'assistant'; content: string; meta?: string };

function SectionList({ title, items, ordered }: { title: string; items?: string[]; ordered?: boolean }) {
  if (!items?.length) return null;
  return (
    <div style={{ marginTop: 16 }}>
      <Typography.Title level={5} style={{ marginBottom: 8 }}>
        {title}
      </Typography.Title>
      {ordered ? (
        <ol style={{ paddingLeft: 20, margin: 0 }}>
          {items.map((x, i) => (
            <li key={i} style={{ marginBottom: 6, lineHeight: 1.6 }}>
              {x}
            </li>
          ))}
        </ol>
      ) : (
        <ul style={{ paddingLeft: 20, margin: 0 }}>
          {items.map((x, i) => (
            <li key={i} style={{ marginBottom: 6, lineHeight: 1.6 }}>
              {x}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function JdResultView({ data }: { data: any }) {
  const text = String(data.externalJd || '')
    .replace(/\\n/g, '\n')
    .trim();

  return (
    <div>
      <Space wrap style={{ marginBottom: 12 }}>
        <Tag color="green">{data.provider || 'hr-agent'}</Tag>
        {data.draft?.id && <Tag>已存草稿</Tag>}
      </Space>

      <Typography.Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>
        {data.title || '职位描述'}
      </Typography.Title>

      <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }} style={{ marginBottom: 8 }}>
        {data.location && <Descriptions.Item label="工作地点">{data.location}</Descriptions.Item>}
        {data.salary && <Descriptions.Item label="薪资范围">{data.salary}</Descriptions.Item>}
        {data.experience && <Descriptions.Item label="经验要求">{data.experience}</Descriptions.Item>}
        {data.education && <Descriptions.Item label="学历要求">{data.education}</Descriptions.Item>}
        {data.headcount != null && data.headcount !== '' && (
          <Descriptions.Item label="招聘人数">{data.headcount}</Descriptions.Item>
        )}
      </Descriptions>

      {!!data.highlights?.length && (
        <Space wrap style={{ marginBottom: 8 }}>
          {data.highlights.map((h: string, i: number) => (
            <Tag key={i} color="blue">
              {h}
            </Tag>
          ))}
        </Space>
      )}

      {data.aboutTeam && (
        <div style={{ marginTop: 8 }}>
          <Typography.Title level={5}>团队/业务简介</Typography.Title>
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>{data.aboutTeam}</Typography.Paragraph>
        </div>
      )}

      <SectionList title="岗位职责" items={data.responsibilities} ordered />
      <SectionList title="任职要求" items={data.requirements} ordered />
      <SectionList title="加分项" items={data.bonuses} ordered />
      <SectionList title="福利待遇" items={data.benefits} />

      {!!data.optimizationTips?.length && (
        <>
          <Divider />
          <SectionList title="优化建议" items={data.optimizationTips} />
        </>
      )}
      {!!data.followUpQuestions?.length && (
        <SectionList title="建议追问业务" items={data.followUpQuestions} ordered />
      )}

      {data.internalJd && (
        <>
          <Divider />
          <Typography.Title level={5}>内部沟通版</Typography.Title>
          <Typography.Paragraph type="secondary" style={{ whiteSpace: 'pre-wrap' }}>
            {String(data.internalJd).replace(/\\n/g, '\n')}
          </Typography.Paragraph>
        </>
      )}

      <Divider />
      <Typography.Title level={5}>对外发布全文（可复制）</Typography.Title>
      <Typography.Paragraph
        copyable={{ text }}
        style={{
          whiteSpace: 'pre-wrap',
          background: '#f6f8f7',
          padding: 12,
          borderRadius: 8,
          marginBottom: 0,
        }}
      >
        {text}
      </Typography.Paragraph>
    </div>
  );
}

function ResultPanel({ result }: { result: { label: string; data: any } }) {
  const isJd = result.label === 'JD生成' || result.data?.externalJd || result.data?.responsibilities;

  return (
    <Card size="small" title={`结果 · ${result.label}`} style={{ marginTop: 16 }}>
      {isJd && result.data?.externalJd ? (
        <JdResultView data={result.data} />
      ) : (
        <pre style={{ maxHeight: 360, overflow: 'auto', margin: 0, whiteSpace: 'pre-wrap' }}>
          {JSON.stringify(result.data, null, 2)}
        </pre>
      )}
    </Card>
  );
}

export default function AgentPage() {
  const [drafts, setDrafts] = useState<any[]>([]);
  const [actions, setActions] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [semantics, setSemantics] = useState<any[]>([]);
  const [queryResult, setQueryResult] = useState<any>(null);
  const [aiHealth, setAiHealth] = useState<any>(null);
  const [capabilities, setCapabilities] = useState<any[]>([]);
  const [chat, setChat] = useState<ChatItem[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<any>(null);
  const { user } = useAuth();

  const load = async () => {
    const [d, a, e, s, h] = await Promise.all([
      api.get('/agent/drafts'),
      api.get('/agent/actions'),
      api.get('/agent/events'),
      api.get('/agent/semantics'),
      api.get('/ai/health').catch(() => ({ data: { ok: false } })),
    ]);
    setDrafts(d.data);
    setActions(a.data);
    setEvents(e.data);
    setSemantics(s.data);
    setAiHealth(h.data);
    try {
      const caps = await api.get('/ai/capabilities');
      setCapabilities(caps.data.capabilities || []);
    } catch {
      setCapabilities([]);
    }
  };

  useEffect(() => {
    load().catch((e) => message.error(e.message));
  }, []);

  const runAi = async (path: string, body: Record<string, unknown>, label: string) => {
    setBusy(true);
    try {
      const { data } = await api.post(path, body);
      setResult({ label, data });
      message.success(`${label} 完成（${data.provider || 'hr-agent'}）`);
      await load();
      return data;
    } catch (e: any) {
      message.error(e.message || '调用失败');
    } finally {
      setBusy(false);
    }
  };

  const sendChat = async () => {
    if (!chatInput.trim()) return;
    const messageText = chatInput.trim();
    setChatInput('');
    setChat((prev) => [...prev, { role: 'user', content: messageText }]);
    setBusy(true);
    try {
      const { data } = await api.post('/ai/chat', {
        message: messageText,
        history: chat.slice(-8),
      });
      setChat((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: data.reply || JSON.stringify(data),
          meta: `${data.kind || 'chat'} · ${data.provider || 'hr-agent'}`,
        },
      ]);
      await load();
    } catch (e: any) {
      setChat((prev) => [...prev, { role: 'assistant', content: `错误：${e.message}` }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="HR Agent 工作台">
      <Typography.Paragraph type="secondary">
        RecruitOS 依赖 HR Agent 提供 AI（理解/生成/推荐）；本系统负责数据、规则、权限与执行。高风险动作必须「建议 → 人工确认 → 执行」。
      </Typography.Paragraph>

      {aiHealth?.ok ? (
        <Alert
          type="success"
          showIcon
          style={{ marginBottom: 12 }}
          message={`HR Agent 已连通（${aiHealth.llm || 'mock'}）`}
          description={aiHealth.url || aiHealth.recruitos}
        />
      ) : (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="HR Agent 未连通"
          description="请另开终端执行 npm run dev:hr-agent（默认 :3002）。未启动时部分 AI 能力会降级或不可用。"
        />
      )}

      <Tabs
        items={[
          {
            key: 'chat',
            label: 'AI 对话',
            children: (
              <>
                <div
                  style={{
                    minHeight: 280,
                    maxHeight: 420,
                    overflow: 'auto',
                    background: '#f6f8f7',
                    padding: 12,
                    marginBottom: 12,
                    borderRadius: 8,
                  }}
                >
                  {chat.length === 0 && (
                    <Typography.Text type="secondary">
                      试试：「帮我分析本月招聘进度」「生成一份 JD」「候选人福利怎么说」
                    </Typography.Text>
                  )}
                  <List
                    dataSource={chat}
                    renderItem={(item) => (
                      <List.Item style={{ border: 'none', padding: '6px 0' }}>
                        <Space direction="vertical" style={{ width: '100%' }} size={0}>
                          <Typography.Text strong>{item.role === 'user' ? '我' : 'HR Agent'}</Typography.Text>
                          {item.meta && (
                            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                              {item.meta}
                            </Typography.Text>
                          )}
                          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                            {item.content}
                          </Typography.Paragraph>
                        </Space>
                      </List.Item>
                    )}
                  />
                </div>
                <Space.Compact style={{ width: '100%' }}>
                  <Input.TextArea
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    placeholder="输入问题，回车发送可用 Ctrl+Enter"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) sendChat();
                    }}
                    disabled={busy}
                  />
                  <Button type="primary" onClick={sendChat} loading={busy} style={{ background: '#1f6b4a' }}>
                    发送
                  </Button>
                </Space.Compact>
              </>
            ),
          },
          {
            key: 'skills',
            label: '场景能力',
            children: (
              <Spin spinning={busy}>
                <Space wrap style={{ marginBottom: 16 }}>
                  {capabilities
                    .filter((c) => c.startable)
                    .map((c) => (
                      <Tag key={c.key} color="green">
                        {c.name}
                      </Tag>
                    ))}
                  {capabilities
                    .filter((c) => !c.startable)
                    .map((c) => (
                      <Tag key={c.key}>{c.name}（暂缓）</Tag>
                    ))}
                </Space>

                <Tabs
                  size="small"
                  items={[
                    {
                      key: 'jd',
                      label: 'JD 生成',
                      children: (
                        <Form
                          layout="vertical"
                          onFinish={(v) => runAi('/ai/jd/generate', v, 'JD生成')}
                          initialValues={{ saveDraft: true }}
                        >
                          <Form.Item name="jobId" label="职位 ID（可选）">
                            <Input placeholder="jobId" />
                          </Form.Item>
                          <Form.Item name="brief" label="需求描述" rules={[{ required: true }]}>
                            <Input.TextArea rows={3} placeholder="例如：需要一个 Java 后端，业务线是供应链" />
                          </Form.Item>
                          <Button type="primary" htmlType="submit" style={{ background: '#1f6b4a' }}>
                            生成 JD
                          </Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'resume',
                      label: '简历解析/初筛',
                      children: (
                        <Space direction="vertical" style={{ width: '100%' }}>
                          <Form layout="inline" onFinish={(v) => runAi('/ai/resume/parse', v, '简历解析')}>
                            <Form.Item name="candidateId" rules={[{ required: true }]} label="候选人ID">
                              <Input style={{ width: 260 }} />
                            </Form.Item>
                            <Button htmlType="submit">解析</Button>
                          </Form>
                          <Form
                            layout="inline"
                            onFinish={(v) => runAi('/ai/resume/screen', v, '语义初筛')}
                          >
                            <Form.Item name="candidateId" rules={[{ required: true }]} label="候选人ID">
                              <Input style={{ width: 200 }} />
                            </Form.Item>
                            <Form.Item name="jobId" rules={[{ required: true }]} label="职位ID">
                              <Input style={{ width: 200 }} />
                            </Form.Item>
                            <Button htmlType="submit">初筛匹配</Button>
                          </Form>
                        </Space>
                      ),
                    },
                    {
                      key: 'schedule',
                      label: '面试协调',
                      children: (
                        <Form
                          layout="inline"
                          onFinish={(v) => runAi('/ai/interview/schedule-assist', v, '面试协调')}
                        >
                          <Form.Item name="applicationId" label="应聘ID">
                            <Input style={{ width: 260 }} />
                          </Form.Item>
                          <Button htmlType="submit">生成可选时段</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'eval',
                      label: '评价汇总',
                      children: (
                        <Form
                          layout="inline"
                          onFinish={(v) => runAi('/ai/interview/summary', v, '评价汇总')}
                        >
                          <Form.Item name="applicationId" rules={[{ required: true }]} label="应聘ID">
                            <Input style={{ width: 260 }} />
                          </Form.Item>
                          <Button htmlType="submit">汇总</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'multimodal',
                      label: 'AI面试测评',
                      children: (
                        <Form
                          layout="vertical"
                          onFinish={(v) => runAi('/ai/interview/multimodal-assess', v, 'AI面试与多模态测评')}
                        >
                          <Form.Item name="applicationId" rules={[{ required: true }]} label="应聘ID">
                            <Input placeholder="applicationId" />
                          </Form.Item>
                          <Form.Item name="transcript" label="面试实录文本（可选）">
                            <Input.TextArea rows={4} placeholder="粘贴面试问答实录，未提供则使用历史评价文本" />
                          </Form.Item>
                          <Form.Item name="audioSignals" label="语音线索（可选）">
                            <Input.TextArea rows={2} placeholder="如：语速偏快、停顿较多、情绪稳定" />
                          </Form.Item>
                          <Form.Item name="videoSignals" label="视频线索（可选）">
                            <Input.TextArea rows={2} placeholder="如：目光交流稳定、肢体表达自然" />
                          </Form.Item>
                          <Button htmlType="submit">生成多维测评</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'talent',
                      label: '人才推荐',
                      children: (
                        <Form
                          layout="inline"
                          onFinish={(v) => runAi('/ai/talent/recommend', v, '人才库推荐')}
                        >
                          <Form.Item name="jobId" rules={[{ required: true }]} label="职位ID">
                            <Input style={{ width: 260 }} />
                          </Form.Item>
                          <Button htmlType="submit">推荐</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'sourcing',
                      label: 'AI寻聘助手',
                      children: (
                        <Form
                          layout="vertical"
                          initialValues={{ channelCode: 'BOSS', submitOutreach: false, autoTag: false }}
                          onFinish={(v) =>
                            runAi('/ai/sourcing/run', {
                              ...v,
                              count: v.count ? Number(v.count) : undefined,
                              submitOutreach: v.submitOutreach === true || v.submitOutreach === 'true',
                              autoTag: v.autoTag === true || v.autoTag === 'true',
                            }, 'AI寻聘助手')
                          }
                        >
                          <Form.Item name="jobId" rules={[{ required: true }]} label="职位ID">
                            <Input placeholder="jobId" />
                          </Form.Item>
                          <Form.Item name="count" label="目标人数（可选）">
                            <Input placeholder="默认10，最大30" />
                          </Form.Item>
                          <Form.Item name="strategy" label="寻访策略（可选）">
                            <Input.TextArea rows={2} placeholder="例如：优先同城、3年以上、有B端系统经验" />
                          </Form.Item>
                          <Form.Item name="channelCode" label="外部渠道">
                            <Select
                              options={[
                                { value: 'BOSS', label: 'Boss直聘' },
                                { value: 'LIEPIN', label: '猎聘' },
                              ]}
                            />
                          </Form.Item>
                          <Form.Item name="submitOutreach" label="提交外部打招呼到人工审核">
                            <Select
                              options={[
                                { value: true, label: '是（生成 PENDING EXTERNAL_OUTREACH）' },
                                { value: false, label: '否（仅生成名单话术）' },
                              ]}
                            />
                          </Form.Item>
                          <Form.Item name="autoTag" label="自动打标签">
                            <Select
                              options={[
                                { value: true, label: '是（写入 AI寻访目标 标签）' },
                                { value: false, label: '否' },
                              ]}
                            />
                          </Form.Item>
                          <Button htmlType="submit">生成寻访名单与话术</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'nurture',
                      label: '候选人问答',
                      children: (
                        <Form layout="vertical" onFinish={(v) => runAi('/ai/nurture/reply', v, '候选人回复')}>
                          <Form.Item name="question" label="候选人问题" rules={[{ required: true }]}>
                            <Input.TextArea rows={2} placeholder="五险一金怎么交？进度如何？" />
                          </Form.Item>
                          <Form.Item name="jobId" label="职位ID（可选）">
                            <Input />
                          </Form.Item>
                          <Button htmlType="submit">生成回复</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'offer',
                      label: 'Offer草稿',
                      children: (
                        <Form layout="vertical" onFinish={(v) => runAi('/ai/offer/draft', v, 'Offer草稿')}>
                          <Form.Item name="applicationId" label="应聘ID" rules={[{ required: true }]}>
                            <Input />
                          </Form.Item>
                          <Form.Item name="packageHint" label="薪资提示（可选，注意敏感）">
                            <Input placeholder="仅草稿占位，正式发送需人工确认" />
                          </Form.Item>
                          <Button htmlType="submit">生成草稿</Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'analytics',
                      label: '数据分析',
                      children: (
                        <Form layout="vertical" onFinish={(v) => runAi('/ai/analytics/ask', v, '运营分析')}>
                          <Form.Item name="question" label="自然语言提问" rules={[{ required: true }]}>
                            <Input.TextArea rows={2} placeholder="本月招聘进度如何？哪个渠道转化最好？" />
                          </Form.Item>
                          <Button type="primary" htmlType="submit" style={{ background: '#1f6b4a' }}>
                            分析
                          </Button>
                        </Form>
                      ),
                    },
                    {
                      key: 'publish',
                      label: '多渠道文案',
                      children: (
                        <Form
                          layout="inline"
                          onFinish={(v) => runAi('/ai/jd/publish-pack', v, '渠道文案包')}
                        >
                          <Form.Item name="jobId" rules={[{ required: true }]} label="职位ID">
                            <Input style={{ width: 260 }} />
                          </Form.Item>
                          <Button htmlType="submit">生成文案</Button>
                        </Form>
                      ),
                    },
                  ]}
                />

                {result && <ResultPanel result={result} />}
              </Spin>
            ),
          },
          {
            key: 'query',
            label: '结构化查询',
            children: (
              <Form
                layout="inline"
                onFinish={async (v) => {
                  try {
                    const { data } = await api.get(`/agent/query/${v.objectType}/${v.id}`);
                    setQueryResult(data);
                  } catch (e: any) {
                    message.error(e.message);
                  }
                }}
              >
                <Form.Item name="objectType" initialValue="application" label="对象">
                  <Select
                    style={{ width: 140 }}
                    options={['job', 'candidate', 'application', 'offer'].map((x) => ({ value: x, label: x }))}
                  />
                </Form.Item>
                <Form.Item name="id" label="ID" rules={[{ required: true }]}>
                  <Input style={{ width: 280 }} placeholder="对象ID" />
                </Form.Item>
                <Button type="primary" htmlType="submit" style={{ background: '#1f6b4a' }}>
                  查询
                </Button>
                {queryResult && (
                  <pre
                    style={{
                      width: '100%',
                      marginTop: 16,
                      maxHeight: 360,
                      overflow: 'auto',
                      background: '#f6f8f7',
                      padding: 12,
                    }}
                  >
                    {JSON.stringify(queryResult, null, 2)}
                  </pre>
                )}
              </Form>
            ),
          },
          {
            key: 'drafts',
            label: '草稿',
            children: (
              <Table
                rowKey="id"
                dataSource={drafts}
                columns={[
                  { title: '类型', dataIndex: 'type' },
                  { title: '来源', dataIndex: 'sourceTag', render: (v) => <Tag color="blue">{v}</Tag> },
                  { title: '内容', dataIndex: 'content', ellipsis: true },
                  { title: '状态', dataIndex: 'status' },
                  {
                    title: '操作',
                    render: (_, row) =>
                      row.status === 'DRAFT' && (
                        <Button
                          type="link"
                          onClick={async () => {
                            await api.post(`/agent/drafts/${row.id}/accept`);
                            load();
                          }}
                        >
                          接受
                        </Button>
                      ),
                  },
                ]}
              />
            ),
          },
          {
            key: 'actions',
            label: '业务动作',
            children: (
              <>
                <Space style={{ marginBottom: 12 }} wrap>
                  <Button
                    onClick={async () => {
                      const { data } = await api.post('/agent/actions', {
                        actionKey: 'ADD_TAG',
                        payload: { candidateId: (await api.get('/candidates')).data[0]?.id, tag: 'Agent标注' },
                        idempotencyKey: `tag-${Date.now()}`,
                      });
                      message.success('低风险动作已执行');
                      console.log(data);
                      load();
                    }}
                  >
                    演示：加标签（低风险）
                  </Button>
                  <Button
                    danger
                    onClick={async () => {
                      const apps = (await api.get('/applications')).data.filter(
                        (a: any) => !['HIRED', 'REJECTED', 'WITHDRAWN'].includes(a.status)
                      );
                      if (!apps[0]) return message.warning('无进行中应聘');
                      const { data } = await api.post('/agent/actions', {
                        actionKey: 'REJECT_CANDIDATE',
                        payload: { applicationId: apps[0].id, reason: 'Agent建议淘汰-待确认', toPool: true },
                        idempotencyKey: `reject-${apps[0].id}-${Date.now()}`,
                      });
                      message.info(data.message || '已提交，待确认');
                      load();
                    }}
                  >
                    演示：淘汰（高风险待确认）
                  </Button>
                </Space>
                <Table
                  rowKey="id"
                  dataSource={actions}
                  columns={[
                    { title: '时间', dataIndex: 'createdAt', render: (v) => dayjs(v).format('MM-DD HH:mm'), width: 110 },
                    { title: '动作', dataIndex: 'actionKey' },
                    {
                      title: '风险',
                      dataIndex: 'riskLevel',
                      render: (v) => <Tag color={v === 'HIGH' ? 'red' : 'green'}>{v}</Tag>,
                    },
                    { title: '状态', dataIndex: 'status' },
                    { title: 'Agent', dataIndex: 'agentId' },
                    {
                      title: '操作',
                      render: (_, row) =>
                        row.status === 'PENDING' &&
                        canRole(user!.role, 'HR', 'RECRUIT_LEAD', 'ADMIN') && (
                          <Space>
                            <Button
                              type="link"
                              onClick={async () => {
                                await api.post(`/agent/actions/${row.id}/confirm`, {});
                                message.success('已确认并执行');
                                load();
                              }}
                            >
                              确认执行
                            </Button>
                            <Button
                              type="link"
                              danger
                              onClick={async () => {
                                await api.post(`/agent/actions/${row.id}/confirm`, { reject: true, reason: '不采纳' });
                                load();
                              }}
                            >
                              拒绝
                            </Button>
                          </Space>
                        ),
                    },
                  ]}
                />
              </>
            ),
          },
          {
            key: 'events',
            label: '事件',
            children: (
              <Table
                rowKey="id"
                dataSource={events}
                columns={[
                  { title: '时间', dataIndex: 'createdAt', render: (v) => dayjs(v).format('MM-DD HH:mm:ss') },
                  { title: '事件', dataIndex: 'eventType' },
                  { title: '对象', dataIndex: 'objectType' },
                  { title: '对象ID', dataIndex: 'objectId', ellipsis: true },
                ]}
              />
            ),
          },
          {
            key: 'semantics',
            label: '语义字典',
            children: (
              <Table
                rowKey="id"
                dataSource={semantics}
                columns={[
                  { title: '分类', dataIndex: 'category' },
                  { title: 'Key', dataIndex: 'key' },
                  { title: '名称', dataIndex: 'label' },
                  { title: '定义', dataIndex: 'definition' },
                ]}
              />
            ),
          },
        ]}
      />
    </Card>
  );
}
