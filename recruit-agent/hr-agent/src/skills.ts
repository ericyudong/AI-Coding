import { chatOrMock, safeJsonParse } from './llm';
import { RecruitOsClient } from './recruitos';

/** 市场市场常见 JD 纯文本（BOSS/猎聘风格） */
function formatStandardJdText(jd: {
  title?: string;
  location?: string;
  salary?: string;
  experience?: string;
  education?: string;
  headcount?: string | number;
  highlights?: string[];
  responsibilities?: string[];
  requirements?: string[];
  bonuses?: string[];
  benefits?: string[];
  aboutTeam?: string;
}) {
  const bullets = (arr?: string[]) =>
    (arr || [])
      .filter(Boolean)
      .map((x, i) => `${i + 1}. ${String(x).replace(/^\d+[\.、)\s]*/, '')}`)
      .join('\n');

  const lines = [
    jd.title || '待定岗位',
    '',
    [
      jd.location && `工作地点：${jd.location}`,
      jd.salary && `薪资范围：${jd.salary}`,
      jd.experience && `经验要求：${jd.experience}`,
      jd.education && `学历要求：${jd.education}`,
      jd.headcount != null && jd.headcount !== '' && `招聘人数：${jd.headcount}`,
    ]
      .filter(Boolean)
      .join('  |  '),
    '',
  ];

  if (jd.highlights?.length) {
    lines.push('【职位亮点】', jd.highlights.map((h) => `· ${h}`).join('\n'), '');
  }
  if (jd.aboutTeam) {
    lines.push('【团队/业务简介】', jd.aboutTeam, '');
  }
  if (jd.responsibilities?.length) {
    lines.push('【岗位职责】', bullets(jd.responsibilities), '');
  }
  if (jd.requirements?.length) {
    lines.push('【任职要求】', bullets(jd.requirements), '');
  }
  if (jd.bonuses?.length) {
    lines.push('【加分项】', bullets(jd.bonuses), '');
  }
  if (jd.benefits?.length) {
    lines.push('【福利待遇】', jd.benefits.map((b) => `· ${b}`).join('\n'), '');
  }

  return lines.filter((x, i, arr) => !(x === '' && arr[i - 1] === '')).join('\n').trim();
}

function normalizeJdNewlines(text: string) {
  return String(text || '')
    .replace(/\\n/g, '\n')
    .replace(/\r\n/g, '\n')
    .trim();
}

/** 1. 职位需求智能诊断与 JD 生成优化 */
export async function generateJd(
  ros: RecruitOsClient,
  input: { jobId?: string; requestId?: string; brief?: string; dialogue?: string[]; saveDraft?: boolean }
) {
  let context: any = {};
  if (input.jobId) {
    try {
      context.job = await ros.query('job', input.jobId);
    } catch {
      /* ignore */
    }
  }
  if (input.requestId) {
    try {
      context.request = await ros.get(`/api/requests/${input.requestId}`);
    } catch {
      /* ignore */
    }
  }

  const title = context.job?.title || context.request?.positionTitle || '待定岗位';
  const location = context.job?.workLocation || context.request?.workLocation || '';
  const salary =
    context.job?.salaryMin || context.request?.salaryMin
      ? `${context.job?.salaryMin || context.request?.salaryMin}-${context.job?.salaryMax || context.request?.salaryMax || ''}K`
      : '';
  const headcount = context.job?.headcount ?? context.request?.headcount ?? '';
  const brief =
    input.brief ||
    input.dialogue?.join('\n') ||
    [context.job?.responsibilities, context.job?.requirements, context.request?.description]
      .filter(Boolean)
      .join('\n') ||
    '';

  const mockStructured = {
    title,
    location: location || '面议',
    salary: salary || '面议',
    experience: '3年以上',
    education: '本科及以上',
    headcount: headcount || 1,
    highlights: ['业务成长快', '技术氛围好', '扁平协作'],
    aboutTeam: brief ? `围绕「${brief}」开展相关业务建设。` : '业务扩张，补充核心岗位编制。',
    responsibilities: [
      '负责相关业务系统的设计、开发与持续优化',
      '与产品、业务紧密协作，推动需求高质量落地',
      '参与技术方案评审，保障系统稳定性与可维护性',
      '沉淀技术规范与最佳实践，推动团队效能提升',
    ],
    requirements: [
      '本科及以上学历，计算机相关专业优先',
      '具备扎实专业技能与可验证的项目落地经验',
      '沟通协作良好，能独立推进跨团队事项',
      '有主人翁意识，结果导向',
    ],
    bonuses: ['有供应链/相关行业背景优先', '有从0到1建设经验优先'],
    benefits: ['五险一金', '带薪年假', '节日福利', '学习成长支持'],
  };

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: `你是资深招聘顾问，按国内招聘平台（BOSS直聘/猎聘）常见 JD 结构输出。
只输出严格 JSON（不要 markdown 代码块），字段如下：
{
  "title":"职位名称",
  "location":"工作地点",
  "salary":"薪资范围，如 20-35K·14薪 或 面议",
  "experience":"经验要求",
  "education":"学历要求",
  "headcount":"招聘人数",
  "highlights":["职位亮点1","亮点2"],
  "aboutTeam":"团队/业务简介，2-3句",
  "responsibilities":["职责1","职责2","职责3","职责4"],
  "requirements":["要求1","要求2","要求3","要求4"],
  "bonuses":["加分项1","加分项2"],
  "benefits":["福利1","福利2"],
  "internalNote":"给用人部门的内部备注",
  "persona":{"mustHave":[],"niceToHave":[],"seniority":""},
  "optimizationTips":["优化建议"],
  "followUpQuestions":["待确认问题"]
}
要求：职责/要求各 4-6 条，具体可执行，避免空话；中文。`,
      },
      {
        role: 'user',
        content: `岗位：${title}
地点：${location || '未提供'}
薪资：${salary || '未提供'}
编制：${headcount || '未提供'}
需求描述：${brief || '未补充'}
组织：${context.job?.org?.name || ''}`,
      },
    ],
    () => JSON.stringify({
      ...mockStructured,
      internalNote: `内部版：${title}\n背景：${brief || '业务扩张补充编制'}\n关注点：业务理解、落地能力、团队协作、稳定性。`,
      persona: {
        mustHave: ['相关岗位经验', '核心技能可验证', '沟通协作'],
        niceToHave: ['对标公司背景', '从0到1经验'],
        seniority: '中级及以上',
      },
      optimizationTips: [
        '建议补充量化成果要求（如系统规模、团队规模、交付周期）',
        '外部 JD 可突出业务场景与成长空间',
        '明确必须技能权重，减少无效简历',
      ],
      followUpQuestions: ['团队规模与汇报关系？', '最关键的 3 项能力权重？', '期望到岗时间与薪资带宽？'],
    }),
    { maxTokens: 1200, retries: 2 }
  );

  const parsed = safeJsonParse(content, null as any);
  const structured = parsed && typeof parsed === 'object' ? { ...mockStructured, ...parsed } : mockStructured;

  // 兼容模型把全文塞进 externalJd 的旧格式
  let externalJd = '';
  if (Array.isArray(structured.responsibilities) && structured.responsibilities.length) {
    externalJd = formatStandardJdText(structured);
  } else if (typeof parsed?.externalJd === 'string') {
    externalJd = normalizeJdNewlines(parsed.externalJd);
  } else {
    externalJd = formatStandardJdText(mockStructured);
  }

  const internalJd =
    normalizeJdNewlines(parsed?.internalNote || parsed?.internalJd || '') ||
    `【内部沟通版】${title}\n背景：${brief || '业务扩张'}\n画像：${JSON.stringify(structured.persona || {})}`;

  const result = {
    title: structured.title || title,
    location: structured.location,
    salary: structured.salary,
    experience: structured.experience,
    education: structured.education,
    headcount: structured.headcount,
    highlights: structured.highlights || [],
    aboutTeam: structured.aboutTeam || '',
    responsibilities: structured.responsibilities || [],
    requirements: structured.requirements || [],
    bonuses: structured.bonuses || [],
    benefits: structured.benefits || [],
    externalJd,
    internalJd,
    persona: structured.persona || {},
    optimizationTips: structured.optimizationTips || [],
    followUpQuestions: structured.followUpQuestions || [],
    provider,
  };

  let draft = null;
  if (input.saveDraft !== false) {
    draft = await ros.saveDraft({
      type: 'JD',
      content: externalJd,
      refType: input.jobId ? 'job' : input.requestId ? 'request' : undefined,
      refId: input.jobId || input.requestId,
    });
  }

  return { ...result, draft };
}

/** 2. 多渠道发布文案包 */
export async function publishPack(
  ros: RecruitOsClient,
  input: { jobId: string; channels?: string[] }
) {
  const job = await ros.query('job', input.jobId);
  const channels = input.channels || ['BOSS', 'LIEPIN', 'INTERNAL', 'REFERRAL'];
  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: '为各招聘渠道生成差异化职位文案。输出 JSON：{packs:[{channel,title,body,tips}]}',
      },
      { role: 'user', content: JSON.stringify({ title: job.title, jd: job.publishCopy || job.responsibilities || job.requirements, channels }) },
    ],
    () =>
      JSON.stringify({
        packs: channels.map((channel) => ({
          channel,
          title: job.title,
          body:
            channel === 'INTERNAL'
              ? `【内推】${job.title}\n地点：${job.workLocation || '待定'}\n欢迎内推，成功入职有奖励。\n${(job.publishCopy || job.responsibilities || '').slice(0, 400)}`
              : `【${channel}】急招 ${job.title}\n工作地点：${job.workLocation || '待定'}\n${(job.publishCopy || job.responsibilities || job.requirements || '详见岗位说明').slice(0, 500)}`,
          tips: channel === 'BOSS' ? '建议精简到 800 字内，突出福利与成长' : '保持与主 JD 关键要求一致',
        })),
      }),
    { json: true }
  );
  const parsed = safeJsonParse(content, { packs: [] });
  const draft = await ros.saveDraft({
    type: 'NOTICE',
    content: JSON.stringify(parsed.packs),
    refType: 'job',
    refId: input.jobId,
  });
  return { ...parsed, provider, draft, job: { id: job.id, title: job.title } };
}

/** 4. 简历解析 */
export async function parseResume(
  ros: RecruitOsClient,
  input: { candidateId: string; resumeText?: string }
) {
  const candidate = await ros.query('candidate', input.candidateId);
  const text =
    input.resumeText ||
    [
      `姓名:${candidate.name}`,
      `电话:${candidate.phone || ''}`,
      `邮箱:${candidate.email || ''}`,
      `学历:${candidate.education || ''}`,
      `学校:${candidate.school || ''}`,
      `公司:${candidate.currentCompany || ''}`,
      `职位:${candidate.currentTitle || ''}`,
      `年限:${candidate.yearsOfExp ?? ''}`,
      candidate.parsedResume || '',
    ].join('\n');

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content:
          '解析简历为结构化 JSON：{education,experience,skills,projects,tags,anomalies,expectedSalary}。anomalies 为异常点数组。',
      },
      { role: 'user', content: text },
    ],
    () =>
      JSON.stringify({
        education: [
          {
            school: candidate.school || '示例大学',
            degree: candidate.education || '本科',
            major: '计算机相关',
          },
        ],
        experience: [
          {
            company: candidate.currentCompany || '未知公司',
            title: candidate.currentTitle || '工程师',
            years: candidate.yearsOfExp || 3,
            highlights: ['主导业务系统建设', '具备跨团队协作与交付能力'],
          },
        ],
        skills: ['业务理解', '项目落地', '沟通协作'],
        projects: [{ name: '核心业务项目', role: '骨干', desc: '从需求到上线闭环交付' }],
        tags: [
          `${candidate.yearsOfExp || 3}年经验`,
          candidate.currentTitle || '工程师',
          candidate.education || '本科',
        ],
        anomalies: candidate.yearsOfExp && candidate.yearsOfExp > 15 ? ['工作年限与教育经历需人工复核'] : [],
        expectedSalary: null,
      }),
    { json: true }
  );

  const parsed = safeJsonParse(content, {});
  const confidence = provider === 'llm' ? 0.9 : candidate.resumePath ? 0.86 : 0.7;

  // 回写候选人结构化字段（经 RecruitOS）
  try {
    await ros.post(`/api/p2/candidates/${input.candidateId}/apply-parse`, {
      parsed,
      confidence,
      source: 'hr-agent',
    });
  } catch {
    // 兼容旧接口：若 apply-parse 不存在，由 RecruitOS 代理层处理
  }

  const draft = await ros.saveDraft({
    type: 'SCREEN',
    content: JSON.stringify({ parsed, confidence }),
    refType: 'candidate',
    refId: input.candidateId,
  });

  return { parsed, confidence, provider, draft, candidateId: input.candidateId };
}

/** 简历语义筛选 */
export async function screenResume(
  ros: RecruitOsClient,
  input: { candidateId: string; jobId: string }
) {
  const [candidate, job] = await Promise.all([
    ros.query('candidate', input.candidateId),
    ros.query('job', input.jobId),
  ]);

  let duplicates: any[] = [];
  try {
    duplicates = await ros.get('/api/p2/candidates/duplicates');
  } catch {
    duplicates = [];
  }
  const dupHit = duplicates.some((g: any) =>
    (g.candidates || []).some((c: any) => c.id === input.candidateId)
  );

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content:
          '基于 JD 语义匹配候选人。输出 JSON：{score0to100,level,reasons,risks,recommendedAction}。level=强烈推荐|一般推荐|待观察|不匹配',
      },
      {
        role: 'user',
        content: JSON.stringify({
          jd: job.responsibilities || job.requirements || job.publishCopy || job.title,
          candidate: {
            name: candidate.name,
            education: candidate.education,
            years: candidate.yearsOfExp,
            title: candidate.currentTitle,
            company: candidate.currentCompany,
            parsed: candidate.parsedResume,
          },
        }),
      },
    ],
    () => {
      const years = candidate.yearsOfExp || 0;
      const score = Math.min(92, 55 + years * 5 + (candidate.education ? 8 : 0));
      const level = score >= 80 ? '强烈推荐' : score >= 65 ? '一般推荐' : score >= 50 ? '待观察' : '不匹配';
      return JSON.stringify({
        score0to100: score,
        level,
        reasons: [
          `岗位「${job.title}」与候选人背景有语义关联`,
          candidate.currentTitle ? `当前职位「${candidate.currentTitle}」与目标方向接近` : '需补充岗位经历细节',
          '建议结合项目成果做二次确认',
        ],
        risks: dupHit ? ['疑似重复投递，请人工核对'] : [],
        recommendedAction: level === '不匹配' ? '淘汰或入库观察' : '进入初筛通过/约面',
      });
    },
    { json: true }
  );

  const result = safeJsonParse<any>(content, {});
  if (dupHit) {
    result.risks = [...(result.risks || []), '疑似重复投递'];
  }

  const draft = await ros.saveDraft({
    type: 'SCREEN',
    content: JSON.stringify(result),
    refType: 'candidate',
    refId: input.candidateId,
  });

  return { ...result, provider, draft, duplicateSuspected: dupHit };
}

/** 5. 人才库推荐 */
export async function recommendTalent(ros: RecruitOsClient, input: { jobId: string; limit?: number }) {
  const job = await ros.query('job', input.jobId);
  let pool: any[] = [];
  try {
    pool = await ros.get('/api/talent-pool');
  } catch {
    pool = [];
  }
  const poolAny: any = pool as any;
  const list = Array.isArray(poolAny) ? poolAny : poolAny?.items || poolAny?.data || [];
  // 人才库接口直接返回 Candidate[]
  const normalized = list.map((p: any) => ({
    id: p.candidateId || p.candidate?.id || p.id,
    name: p.candidate?.name || p.name,
    tags: p.tags || p.poolCategory || p.category,
    reason: p.poolRemark || p.reason,
  }));

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: '从人才库挑选适合岗位的候选人。输出 JSON：{recommendations:[{candidateId,name,score,reason,activateMessage}]}',
      },
      {
        role: 'user',
        content: JSON.stringify({
          job: { id: job.id, title: job.title, jd: job.responsibilities || job.requirements },
          pool: normalized.slice(0, 30),
        }),
      },
    ],
    () => {
      const picks = normalized.slice(0, input.limit || 5).map((p: any, i: number) => ({
        candidateId: p.id,
        name: p.name || '候选人',
        score: 88 - i * 4,
        reason: `与「${job.title}」技能/背景匹配，建议激活触达`,
        activateMessage: `您好，我们有新岗位「${job.title}」与您背景较匹配，方便聊聊意向吗？`,
      }));
      return JSON.stringify({ recommendations: picks });
    },
    { json: true }
  );

  return { ...safeJsonParse(content, { recommendations: [] }), provider, jobId: job.id, jobTitle: job.title };
}

/** 3. AI 寻聘助手（站内寻访 + 可选提交外部渠道人工审核） */
export async function sourcingAssistant(
  ros: RecruitOsClient,
  input: {
    jobId: string;
    count?: number;
    strategy?: string;
    autoTag?: boolean;
    /** 提交外部打招呼到人工审核闸门 */
    submitOutreach?: boolean;
    channelCode?: string;
  }
) {
  const [job, allCandidates, pool] = await Promise.all([
    ros.query('job', input.jobId),
    ros.get('/api/candidates').catch(() => []),
    ros.get('/api/talent-pool').catch(() => []),
  ]);
  const baseList = Array.isArray(pool) && pool.length ? pool : Array.isArray(allCandidates) ? allCandidates : [];
  const count = Math.max(1, Math.min(Number(input.count) || 10, 30));

  const shortlist = baseList.slice(0, 80).map((c: any) => ({
    candidateId: c.candidateId || c.id,
    name: c.candidate?.name || c.name,
    currentTitle: c.candidate?.currentTitle || c.currentTitle,
    company: c.candidate?.currentCompany || c.currentCompany,
    yearsOfExp: c.candidate?.yearsOfExp || c.yearsOfExp,
    tags: c.tags || c.poolCategory || c.category,
    city: c.candidate?.city || c.city,
  }));

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content:
          '你是招聘寻访助手。根据岗位需求从候选池中挑选名单，并生成首轮沟通话术。输出 JSON：{strategy,targets:[{candidateId,name,score,reason,openingMessage,askPoints}],marketHints,complianceNote}',
      },
      {
        role: 'user',
        content: JSON.stringify({
          job: {
            id: job.id,
            title: job.title,
            location: job.workLocation,
            jd: `${job.responsibilities || ''}\n${job.requirements || ''}`,
          },
          strategy: input.strategy || '优先同城+相关岗位+3年以上经验',
          candidates: shortlist,
          count,
        }),
      },
    ],
    () =>
      JSON.stringify({
        strategy: input.strategy || '优先同城+相关岗位+3年以上经验',
        targets: shortlist.slice(0, count).map((c: any, i: number) => ({
          candidateId: c.candidateId,
          name: c.name || `候选人${i + 1}`,
          score: 90 - i,
          reason: `与岗位「${job.title}」方向匹配，具备相关经历`,
          openingMessage: `您好，我是 RecruitOS 招聘顾问。我们有一个「${job.title}」岗位与您的背景比较匹配，方便聊下近期机会吗？`,
          askPoints: ['当前求职意向', '期望薪资区间', '最快到岗时间'],
        })),
        marketHints: ['建议优先触达近30天活跃候选人', '同类公司背景候选人回复率更高'],
        complianceNote: '外部渠道触达须经人工审核闸门；默认不直接调用外部平台。',
      }),
    { maxTokens: 1200, retries: 2 }
  );

  const parsed = safeJsonParse<any>(content, { targets: [] as any[] });
  const targets = Array.isArray(parsed.targets) ? parsed.targets : [];

  if (input.autoTag) {
    for (const t of targets.slice(0, 20)) {
      if (!t.candidateId) continue;
      try {
        await ros.proposeAction({
          actionKey: 'ADD_TAG',
          payload: { candidateId: t.candidateId, tag: 'AI寻访目标' },
          idempotencyKey: `sourcing-tag-${input.jobId}-${t.candidateId}`,
        });
      } catch {
        // ignore
      }
    }
  }

  let outreachSubmit: any = null;
  if (input.submitOutreach && targets.length) {
    const channelCode = String(input.channelCode || 'BOSS').toUpperCase();
    try {
      outreachSubmit = await ros.post('/api/channels/outreach/submit', {
        jobId: input.jobId,
        channelCode,
        items: targets.map((t: any) => ({
          candidateId: t.candidateId,
          candidateName: t.name,
          message: t.openingMessage,
        })),
      });
    } catch (e: any) {
      outreachSubmit = { error: e.message || '提交审核失败' };
    }
  }

  const draft = await ros.saveDraft({
    type: 'NOTICE',
    content: JSON.stringify({ jobId: input.jobId, strategy: parsed.strategy, targets, outreachSubmit }),
    refType: 'job',
    refId: input.jobId,
  });

  return {
    provider,
    job: { id: job.id, title: job.title },
    strategy: parsed.strategy || input.strategy,
    targets,
    marketHints: parsed.marketHints || [],
    complianceNote:
      parsed.complianceNote ||
      '站内生成名单与话术；若开启 submitOutreach，将提交 EXTERNAL_OUTREACH 待人工确认后由渠道适配层执行。',
    outreachSubmit,
    draft,
  };
}

/** 6. 面试日程协调建议 */
export async function scheduleAssist(
  ros: RecruitOsClient,
  input: { applicationId?: string; interviewId?: string; preferredDays?: number }
) {
  let application: any = null;
  if (input.applicationId) {
    application = await ros.query('application', input.applicationId);
  }
  let busy: any = null;
  try {
    busy = await ros.get('/api/p2/calendar/busy');
  } catch {
    busy = { slots: [] };
  }

  const days = input.preferredDays || 5;
  const suggestions: { start: string; end: string; label: string }[] = [];
  const base = new Date();
  base.setHours(10, 0, 0, 0);
  for (let d = 1; d <= days + 2 && suggestions.length < 3; d++) {
    const start = new Date(base);
    start.setDate(base.getDate() + d);
    if (start.getDay() === 0 || start.getDay() === 6) continue;
    const end = new Date(start);
    end.setHours(11, 0, 0, 0);
    suggestions.push({
      start: start.toISOString(),
      end: end.toISOString(),
      label: `${start.getMonth() + 1}/${start.getDate()} 10:00-11:00`,
    });
  }

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: '根据忙闲生成面试邀约文案与协调说明。输出 JSON：{messageToCandidate,messageToInterviewers,notes}',
      },
      {
        role: 'user',
        content: JSON.stringify({
          candidate: application?.candidate?.name,
          job: application?.job?.title,
          suggestions,
          busy,
        }),
      },
    ],
    () =>
      JSON.stringify({
        messageToCandidate: `您好${application?.candidate?.name ? ' ' + application.candidate.name : ''}，关于「${application?.job?.title || '岗位'}」面试，请从以下时段选择：\n${suggestions.map((s) => `- ${s.label}`).join('\n')}\n确认后将发送会议信息。`,
        messageToInterviewers: `请预留以下候选时段用于面试协调：\n${suggestions.map((s) => `- ${s.label}`).join('\n')}`,
        notes: '已避开周末；正式锁定前请人工确认面试官日历无冲突。',
      }),
    { json: true }
  );

  const draft = await ros.saveDraft({
    type: 'NOTICE',
    content: content,
    refType: input.applicationId ? 'application' : 'interview',
    refId: input.applicationId || input.interviewId,
  });

  return { suggestions, ...safeJsonParse(content, {}), provider, draft };
}

/** 8. 面试评价汇总 */
export async function interviewSummary(ros: RecruitOsClient, input: { applicationId: string }) {
  const application = await ros.query('application', input.applicationId);
  const interviews = application.interviews || [];
  const evals = interviews.flatMap((i: any) => i.evaluations || []);

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content:
          '汇总多轮面试评价，生成综合报告。输出 JSON：{summary,strengths,risks,suggestedDecision,radarNotes}。高风险决策仅建议，不直接下结论执行。',
      },
      {
        role: 'user',
        content: JSON.stringify({
          candidate: application.candidate?.name,
          job: application.job?.title,
          status: application.status,
          evaluations: evals.map((e: any) => ({
            overall: e.overall,
            recommendation: e.recommendation,
            comment: e.comment,
            scores: e.scores,
          })),
        }),
      },
    ],
    () => {
      const pass = evals.filter((e: any) => String(e.recommendation || '').includes('PASS') || e.overall >= 3).length;
      const fail = evals.filter((e: any) => String(e.recommendation || '').includes('FAIL') || e.overall <= 2).length;
      return JSON.stringify({
        summary: `候选人「${application.candidate?.name}」申请「${application.job?.title}」，共 ${evals.length} 份评价，通过倾向 ${pass}、保留/不通过倾向 ${fail}。`,
        strengths: ['业务理解与沟通表达', '项目经历可验证'],
        risks: evals.length < 2 ? ['评价样本偏少，建议补一轮交叉验证'] : ['需关注稳定性与到岗时间'],
        suggestedDecision: pass >= fail ? '建议进入下一轮或录用讨论（需人工确认）' : '建议谨慎推进或入库（需人工确认）',
        radarNotes: '六维雷达请以各轮评分均值为准，终面决策必须人工确认。',
      });
    },
    { json: true }
  );

  const draft = await ros.saveDraft({
    type: 'EVAL_SUMMARY',
    content,
    refType: 'application',
    refId: input.applicationId,
  });

  return { ...safeJsonParse(content, {}), provider, draft, evaluationCount: evals.length };
}

/** 7. AI 面试与多模态测评（文本增强版） */
export async function multimodalInterviewAssess(
  ros: RecruitOsClient,
  input: { applicationId: string; transcript?: string; audioSignals?: string; videoSignals?: string }
) {
  const application = await ros.query('application', input.applicationId);
  const interviews = application.interviews || [];
  const evals = interviews.flatMap((i: any) => i.evaluations || []);

  const transcript =
    input.transcript ||
    evals
      .map((e: any) => [e.strengths, e.risks, e.overall].filter(Boolean).join('\n'))
      .filter(Boolean)
      .join('\n');

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content:
          '你是面试测评助手。基于文本、语音线索、视频线索输出评估 JSON：{dimensions,summary,riskFlags,followUpQuestions,recommendation,decisionBoundary}。其中 decisionBoundary 必须强调“仅辅助，最终由人工决定”。',
      },
      {
        role: 'user',
        content: JSON.stringify({
          candidate: application.candidate?.name,
          job: application.job?.title,
          transcript,
          audioSignals: input.audioSignals || '无结构化语音信号（待接入）',
          videoSignals: input.videoSignals || '无结构化视频信号（待接入）',
          historicalEvaluations: evals.map((e: any) => ({
            overall: e.overall,
            conclusion: e.conclusion,
            strengths: e.strengths,
            risks: e.risks,
          })),
        }),
      },
    ],
    () =>
      JSON.stringify({
        dimensions: [
          { key: 'content', label: '回答内容质量', score: 78, reason: '经历与岗位相关，回答结构较清晰' },
          { key: 'logic', label: '逻辑表达', score: 74, reason: '能说明问题与结果，细节量化仍可加强' },
          { key: 'collaboration', label: '协作沟通', score: 80, reason: '跨团队沟通意识较好' },
          { key: 'stability', label: '稳定性与动机', score: 70, reason: '动机积极，需确认长期规划与到岗周期' },
        ],
        summary: `候选人「${application.candidate?.name}」在「${application.job?.title}」评估中整体表现中上，建议进入下一轮深挖关键能力。`,
        riskFlags: ['关键项目指标描述不够量化', '对复杂冲突场景的处置案例可进一步追问'],
        followUpQuestions: ['请给出最近一个复杂项目的量化结果', '面对跨部门冲突你如何推进达成共识？'],
        recommendation: '建议进入下一轮/录用讨论（人工确认后执行）',
        decisionBoundary: '本结果仅作辅助参考，不可替代终面官与业务负责人最终决策。',
      }),
    { maxTokens: 1000, retries: 2 }
  );

  const parsed = safeJsonParse<any>(content, {});
  const draft = await ros.saveDraft({
    type: 'EVAL_SUMMARY',
    content: JSON.stringify(parsed),
    refType: 'application',
    refId: input.applicationId,
  });

  return {
    ...parsed,
    provider,
    mode: 'text-enhanced-multimodal',
    note: '当前版本采用文本增强多维评估，真实音视频特征接入后可升级为全量多模态评分。',
    draft,
  };
}

/** 9. 候选人问答 / 体验沟通 */
export async function nurtureReply(
  ros: RecruitOsClient,
  input: { question: string; jobId?: string; applicationId?: string; intent?: string }
) {
  let job: any = null;
  if (input.jobId) {
    try {
      job = await ros.query('job', input.jobId);
    } catch {
      /* */
    }
  }
  if (!job && input.applicationId) {
    const app = await ros.query('application', input.applicationId);
    job = app.job;
  }

  const kb = [
    '五险一金按政策缴纳，具体比例以入职通知为准。',
    '年假与法定节假日按公司制度执行。',
    '加班按项目节奏安排，鼓励高效交付。',
    '投递后通常 3 个工作日内反馈初筛结果。',
  ];

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: '你是企业招聘候选人体验管家。语气专业有温度，不确定的不编造。输出 JSON：{reply,suggestedStatusUpdate,tone}',
      },
      {
        role: 'user',
        content: JSON.stringify({ question: input.question, job, kb, intent: input.intent }),
      },
    ],
    () => {
      const q = input.question || '';
      let reply = '感谢关注。我已记录您的问题，HR 将尽快回复。';
      if (/薪|工资|待遇/.test(q)) reply = '薪资结构与带宽会在进入录用沟通阶段由 HR 与您当面确认，初筛阶段以岗位匹配为主。';
      else if (/保险|五险|公积金/.test(q)) reply = kb[0];
      else if (/年假|加班|福利/.test(q)) reply = `${kb[1]} ${kb[2]}`;
      else if (/进度|结果|多久/.test(q)) reply = kb[3] + (job ? ` 您咨询的岗位为「${job.title}」。` : '');
      else if (/拒|不合适/.test(q))
        reply = '感谢您的时间与兴趣。本次暂未进入下一环节，我们已将您保留在人才库，后续有匹配机会会优先联系。';
      return JSON.stringify({
        reply,
        suggestedStatusUpdate: null,
        tone: 'warm',
      });
    },
    { json: true }
  );

  const draft = await ros.saveDraft({
    type: 'NOTICE',
    content,
    refType: input.applicationId ? 'application' : 'job',
    refId: input.applicationId || input.jobId,
  });

  return { ...safeJsonParse(content, { reply: content }), provider, draft };
}

/** 10. Offer 草稿 */
export async function offerDraft(ros: RecruitOsClient, input: { applicationId: string; packageHint?: string }) {
  const application = await ros.query('application', input.applicationId);
  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content:
          '生成 Offer 文案草稿（不含敏感薪资明文时可留占位）。输出 JSON：{subject,body,onboardingChecklist,followUpReminders}。注意：仅草稿，发送需人工确认。',
      },
      {
        role: 'user',
        content: JSON.stringify({
          candidate: application.candidate?.name,
          job: application.job?.title,
          location: application.job?.workLocation,
          packageHint: input.packageHint,
        }),
      },
    ],
    () =>
      JSON.stringify({
        subject: `录用通知 — ${application.job?.title || '岗位'}`,
        body: [
          `尊敬的 ${application.candidate?.name || '候选人'}：`,
          '',
          `恭喜您通过「${application.job?.title || '岗位'}」招聘流程。现向您发出录用意向。`,
          `工作地点：${application.job?.workLocation || '以沟通确认为准'}`,
          `薪资与福利：${input.packageHint || '【待填写，敏感信息请人工确认后填入】'}`,
          '入职日期：【待确认】',
          '',
          '请于收到本通知后 3 个工作日内回复是否接受。',
          '',
          '此为 AI 生成草稿，正式发送前须经审批与人工确认。',
        ].join('\n'),
        onboardingChecklist: ['身份证/学历证明', '离职证明', '银行卡信息', '体检报告', '入职登记表'],
        followUpReminders: ['发送后 D+1 提醒确认', '入职前 3 天推送材料清单', '入职前 1 天工位/账号准备提醒'],
      }),
    { json: true }
  );

  const draft = await ros.saveDraft({
    type: 'OFFER',
    content,
    refType: 'application',
    refId: input.applicationId,
  });

  return { ...safeJsonParse(content, {}), provider, draft, riskNote: '发送 Offer 为高风险动作，须经 RecruitOS 人工确认执行' };
}

/** 11. 自然语言分析 */
export async function analyticsAsk(ros: RecruitOsClient, input: { question: string }) {
  const [overview, funnel] = await Promise.all([
    ros.overview().catch(() => ({ requests: [] })),
    ros.funnel().catch(() => ({})),
  ]);
  let channel: any = null;
  try {
    channel = await ros.channelRoi();
  } catch {
    channel = null;
  }

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: '你是招聘运营分析师。基于数据回答管理者问题，给出洞察与优化建议。输出 JSON：{answer,insights,actions,dataHighlights}',
      },
      {
        role: 'user',
        content: JSON.stringify({ question: input.question, overview, funnel, channel }),
      },
    ],
    () => {
      const reqs = overview.requests || [];
      const open = reqs.filter((r: any) => r.status === 'OPEN' || r.status === 'IN_PROGRESS' || r.gap > 0);
      const totalGap = reqs.reduce((s: any, r: any) => s + (r.gap || 0), 0);
      return JSON.stringify({
        answer: `当前共 ${reqs.length} 条需求相关记录，待补缺口约 ${totalGap} 人。漏斗数据已接入，可继续追问具体岗位或渠道。问题：「${input.question}」`,
        insights: [
          open.length ? `仍有 ${open.length} 个需求存在缺口，建议聚焦高优先级岗位` : '需求缺口整体可控',
          '建议按周复盘初筛通过率与面试到场率，定位卡点',
        ],
        actions: ['对转化低的渠道降权或优化 JD', '对周期过长岗位启动人才库激活', '对爽约率高的场次加强提醒'],
        dataHighlights: { requestCount: reqs.length, totalGap, funnel },
      });
    },
    { json: true }
  );

  return { ...safeJsonParse(content, { answer: content }), provider };
}

/** 通用对话（可触发工具意图） */
export async function chat(
  ros: RecruitOsClient,
  input: { message: string; history?: { role: string; content: string }[]; context?: Record<string, string> }
) {
  const msg = input.message || '';
  const ctx = input.context || {};

  // 轻量意图路由（无 LLM 时仍可用）
  if (/生成.*JD|写.*职位|优化.*JD/i.test(msg) || ctx.intent === 'jd') {
    const r = await generateJd(ros, { jobId: ctx.jobId, requestId: ctx.requestId, brief: msg, saveDraft: true });
    return { reply: r.externalJd || JSON.stringify(r), kind: 'jd', data: r, provider: r.provider };
  }
  if (/解析.*简历|初筛|匹配度/i.test(msg) || ctx.intent === 'screen') {
    if (ctx.candidateId && ctx.jobId) {
      const r = await screenResume(ros, { candidateId: ctx.candidateId, jobId: ctx.jobId });
      return {
        reply: `匹配结论：${r.level}（${r.score0to100}分）。${(r.reasons || []).join('；')}`,
        kind: 'screen',
        data: r,
        provider: r.provider,
      };
    }
  }
  if (/报表|漏斗|渠道|进度|分析|转化|周期/i.test(msg) || ctx.intent === 'analytics') {
    const r = await analyticsAsk(ros, { question: msg });
    return { reply: r.answer, kind: 'analytics', data: r, provider: r.provider };
  }
  if (/约面|面试时间|排期/i.test(msg) || ctx.intent === 'schedule') {
    const r = await scheduleAssist(ros, { applicationId: ctx.applicationId });
    return {
      reply: (r as any).messageToCandidate || JSON.stringify((r as any).suggestions || []),
      kind: 'schedule',
      data: r,
      provider: r.provider,
    };
  }
  if (/寻访|找人|主动搜寻|sourcing/i.test(msg) || ctx.intent === 'sourcing') {
    if (ctx.jobId) {
      const r = await sourcingAssistant(ros, { jobId: ctx.jobId, strategy: msg, autoTag: false });
      return {
        reply: `已生成 ${r.targets?.length || 0} 位寻访目标，首位候选人：${r.targets?.[0]?.name || '无'}。`,
        kind: 'sourcing',
        data: r,
        provider: r.provider,
      };
    }
  }
  if (/多模态|面试测评|AI面试|综合测评/i.test(msg) || ctx.intent === 'multimodal_interview') {
    if (ctx.applicationId) {
      const r = await multimodalInterviewAssess(ros, { applicationId: ctx.applicationId });
      return {
        reply: r.summary || '已生成多维测评草稿，请查看详情并人工决策。',
        kind: 'multimodal_interview',
        data: r,
        provider: r.provider,
      };
    }
  }

  const { content, provider } = await chatOrMock(
    [
      {
        role: 'system',
        content: `你是 HR Agent，服务于招聘管理系统 RecruitOS。
可协助：JD生成、简历初筛、人才库推荐、AI寻访、面试协调、评价汇总、AI面试测评、候选人问答、Offer草稿、招聘数据分析。
高风险动作（淘汰、发Offer等）只给建议，由系统确认后执行。
用简洁中文回答。`,
      },
      ...(input.history || []).slice(-8).map((h) => ({
        role: (h.role === 'assistant' ? 'assistant' : 'user') as 'user' | 'assistant',
        content: h.content,
      })),
      { role: 'user' as const, content: msg },
    ],
    () =>
      [
        '我是 HR Agent，已与 RecruitOS 打通。',
        '你可以这样问我：',
        '· 「帮我生成/优化 JD」',
        '· 「分析本月招聘进度」',
        '· 「给候选人写回复」',
        '· 在能力面板选择具体场景并带上 jobId / candidateId',
        '',
        `你刚说：${msg}`,
      ].join('\n')
  );

  return { reply: content, kind: 'chat', provider };
}
