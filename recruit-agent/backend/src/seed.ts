import bcrypt from 'bcryptjs';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function main() {
  await prisma.hireQualityRecord.deleteMany();
  await prisma.semanticDict.deleteMany();
  await prisma.eventSubscription.deleteMany();
  await prisma.businessEvent.deleteMany();
  await prisma.agentAction.deleteMany();
  await prisma.agentDraft.deleteMany();
  await prisma.calendarBusy.deleteMany();
  await prisma.talentActivationItem.deleteMany();
  await prisma.talentActivation.deleteMany();
  await prisma.onboardCollabTask.deleteMany();
  await prisma.warmTask.deleteMany();
  await prisma.alertEvent.deleteMany();
  await prisma.alertSubscription.deleteMany();
  await prisma.slaRule.deleteMany();
  await prisma.candidateFeedback.deleteMany();
  await prisma.messageLog.deleteMany();
  await prisma.secureLink.deleteMany();
  await prisma.jobChannelPublish.deleteMany();
  await prisma.channelAccount.deleteMany();
  await prisma.channel.deleteMany();
  await prisma.flowNode.deleteMany();
  await prisma.flowTemplate.deleteMany();
  await prisma.evalModel.deleteMany();
  await prisma.jobStandard.deleteMany();
  await prisma.auditLog.deleteMany();
  await prisma.activity.deleteMany();
  await prisma.todo.deleteMany();
  await prisma.interviewEvaluation.deleteMany();
  await prisma.interviewInterviewer.deleteMany();
  await prisma.interview.deleteMany();
  await prisma.processEvent.deleteMany();
  await prisma.onboarding.deleteMany();
  await prisma.offer.deleteMany();
  await prisma.application.deleteMany();
  await prisma.candidateRemark.deleteMany();
  await prisma.candidate.deleteMany();
  await prisma.job.deleteMany();
  await prisma.recruitRequest.deleteMany();
  await prisma.template.deleteMany();
  await prisma.dictionary.deleteMany();
  await prisma.user.deleteMany();
  await prisma.organization.deleteMany();

  const root = await prisma.organization.create({ data: { name: '示例科技有限公司' } });
  const eng = await prisma.organization.create({ data: { name: '研发中心', parentId: root.id } });
  const hr = await prisma.organization.create({ data: { name: '人力资源部', parentId: root.id } });
  const product = await prisma.organization.create({ data: { name: '产品部', parentId: root.id } });

  const passwordHash = await bcrypt.hash('123456', 10);
  const users = await Promise.all([
    prisma.user.create({
      data: { username: 'admin', passwordHash, name: '系统管理员', role: 'ADMIN', orgId: hr.id, dataScope: 'ALL', email: 'admin@example.com' },
    }),
    prisma.user.create({
      data: { username: 'lead', passwordHash, name: '张招聘负责人', role: 'RECRUIT_LEAD', orgId: hr.id, dataScope: 'ALL', email: 'lead@example.com' },
    }),
    prisma.user.create({
      data: { username: 'hr', passwordHash, name: '李招聘HR', role: 'HR', orgId: hr.id, dataScope: 'SELF', email: 'hr@example.com' },
    }),
    prisma.user.create({
      data: { username: 'dept', passwordHash, name: '王部门负责人', role: 'DEPT_HEAD', orgId: eng.id, dataScope: 'DEPT', email: 'dept@example.com' },
    }),
    prisma.user.create({
      data: { username: 'interviewer', passwordHash, name: '赵面试官', role: 'INTERVIEWER', orgId: eng.id, dataScope: 'SELF', email: 'iv@example.com' },
    }),
    prisma.user.create({
      data: { username: 'approver', passwordHash, name: '钱Offer审批', role: 'OFFER_APPROVER', orgId: hr.id, dataScope: 'ALL', email: 'offer@example.com' },
    }),
    prisma.user.create({
      data: { username: 'ops', passwordHash, name: '孙人事运营', role: 'HR_OPS', orgId: hr.id, dataScope: 'ALL', email: 'ops@example.com' },
    }),
    prisma.user.create({
      data: { username: 'viewer', passwordHash, name: '周数据查看', role: 'DATA_VIEWER', orgId: root.id, dataScope: 'ALL', email: 'viewer@example.com' },
    }),
  ]);

  const [, lead, hrUser, deptHead, interviewer] = users;

  const dicts = [
    ['RECRUIT_REASON', 'NEW', '新增编制'],
    ['RECRUIT_REASON', 'REPLACE', '人员替补'],
    ['RECRUIT_REASON', 'PROJECT', '业务项目'],
    ['RECRUIT_REASON', 'OTHER', '其他'],
    ['SOURCE', 'SITE', '招聘网站'],
    ['SOURCE', 'REFERRAL', '内推'],
    ['SOURCE', 'HUNTER', '猎头'],
    ['SOURCE', 'POOL', '人才库'],
    ['SOURCE', 'DIRECT', '主动投递'],
    ['SOURCE', 'OTHER', '其他'],
    ['REJECT_REASON', 'MISMATCH', '不匹配'],
    ['REJECT_REASON', 'EXP', '经验不足'],
    ['REJECT_REASON', 'SALARY', '薪资不符'],
    ['REJECT_REASON', 'QUIT', '候选人放弃'],
    ['REJECT_REASON', 'CLOSED', '岗位关闭'],
    ['OFFER_DECLINE', 'SALARY', '薪酬'],
    ['OFFER_DECLINE', 'LOCATION', '地点'],
    ['OFFER_DECLINE', 'GROWTH', '发展'],
    ['OFFER_DECLINE', 'COMPETE', '竞对Offer'],
    ['OFFER_DECLINE', 'PERSONAL', '个人原因'],
    ['ABANDON_REASON', 'OTHER_OFFER', '接受其他Offer'],
    ['ABANDON_REASON', 'PERSONAL', '个人原因'],
    ['ABANDON_REASON', 'SALARY', '薪酬变动'],
    ['EDUCATION', 'BACHELOR', '本科'],
    ['EDUCATION', 'MASTER', '硕士'],
    ['EDUCATION', 'PHD', '博士'],
    ['EDUCATION', 'COLLEGE', '大专'],
    ['CITY', 'BJ', '北京'],
    ['CITY', 'SH', '上海'],
    ['CITY', 'SZ', '深圳'],
    ['CITY', 'HZ', '杭州'],
    ['LEVEL', 'P5', 'P5'],
    ['LEVEL', 'P6', 'P6'],
    ['LEVEL', 'P7', 'P7'],
  ];
  for (let i = 0; i < dicts.length; i++) {
    const [type, code, label] = dicts[i];
    await prisma.dictionary.create({ data: { type, code, label, sort: i } });
  }

  await prisma.template.createMany({
    data: [
      {
        type: 'EVAL',
        name: '通用面试评价模板',
        content: JSON.stringify({
          dimensions: [
            { key: 'professional', label: '专业能力' },
            { key: 'experience', label: '相关经验' },
            { key: 'problemSolving', label: '问题解决' },
            { key: 'communication', label: '沟通协作' },
            { key: 'motivation', label: '动机与稳定性' },
            { key: 'values', label: '价值观风险' },
          ],
        }),
      },
      {
        type: 'INTERVIEW_NOTICE',
        name: '标准面试通知',
        content: '【面试通知】候选人：{{candidate}} 职位：{{job}} 时间：{{time}} 方式：{{method}} 地点/链接：{{place}}',
      },
      {
        type: 'OFFER',
        name: '标准Offer模板',
        content: '录用通知书标准模板',
      },
      {
        type: 'ONBOARDING_MATERIALS',
        name: '入职材料清单',
        content: JSON.stringify(['身份证复印件', '学历证明', '离职证明', '体检报告', '银行卡信息']),
      },
    ],
  });

  const expectDate = new Date();
  expectDate.setDate(expectDate.getDate() + 30);

  const request = await prisma.recruitRequest.create({
    data: {
      name: '研发中心高级前端工程师2人',
      orgId: eng.id,
      positionTitle: '高级前端工程师',
      headcount: 2,
      reason: '新增编制',
      expectDate,
      workLocation: '北京',
      salaryMin: 25,
      salaryMax: 40,
      deptHeadId: deptHead.id,
      hrOwnerId: hrUser.id,
      ownerId: deptHead.id,
      description: '支撑招聘管理系统与HR Agent平台前端建设',
      status: 'RECRUITING',
      approvedAt: new Date(),
      approvedBy: lead.id,
    },
  });

  const job = await prisma.job.create({
    data: {
      requestId: request.id,
      orgId: eng.id,
      title: '高级前端工程师',
      headcount: 2,
      workLocation: '北京',
      salaryMin: 25,
      salaryMax: 40,
      responsibilities: '1. 负责招聘管理系统前端架构与核心页面开发\n2. 与后端协作完成业务流程闭环\n3. 保障交互体验与性能',
      requirements: '1. 3年以上前端经验\n2. 熟悉 React/TypeScript\n3. 有企业后台系统经验优先',
      bonuses: '有 Ant Design / 招聘 SaaS 经验加分',
      hrOwnerId: hrUser.id,
      status: 'OPEN',
      publishCopy: '【招聘】高级前端工程师\n部门：研发中心\n地点：北京\n人数：2',
    },
  });

  const candidates = await Promise.all([
    prisma.candidate.create({
      data: {
        name: '候选A-筛选淘汰',
        phone: '13800000001',
        email: 'a@example.com',
        education: '本科',
        currentCompany: '甲公司',
        currentTitle: '前端工程师',
        yearsOfExp: 2,
        city: '北京',
        source: '招聘网站',
      },
    }),
    prisma.candidate.create({
      data: {
        name: '候选B-面试淘汰入库',
        phone: '13800000002',
        email: 'b@example.com',
        education: '硕士',
        currentCompany: '乙公司',
        currentTitle: '高级前端',
        yearsOfExp: 5,
        city: '北京',
        source: '内推',
        sourceRemark: '同事推荐',
        inTalentPool: true,
        poolCategory: '前端',
        poolRemark: '能力不错但暂不匹配当前JD，入库备选',
      },
    }),
    prisma.candidate.create({
      data: {
        name: '候选C-完整入职',
        phone: '13800000003',
        email: 'c@example.com',
        education: '本科',
        school: '示例大学',
        currentCompany: '丙公司',
        currentTitle: '前端负责人',
        yearsOfExp: 6,
        city: '北京',
        expectSalary: '35K',
        source: '主动投递',
      },
    }),
  ]);

  // A rejected at screen
  const appA = await prisma.application.create({
    data: {
      candidateId: candidates[0].id,
      jobId: job.id,
      status: 'REJECTED',
      stage: 'HR_SCREEN',
      screenResult: 'REJECT',
      screenReason: '经验不足',
      rejectReason: '经验不足',
    },
  });
  await prisma.processEvent.createMany({
    data: [
      { applicationId: appA.id, type: 'ENTER', toStatus: 'HR_SCREEN', operatorName: '李招聘HR' },
      { applicationId: appA.id, type: 'REJECT', fromStatus: 'HR_SCREEN', toStatus: 'REJECTED', reason: '经验不足', operatorName: '李招聘HR' },
    ],
  });

  // B rejected after interview -> talent pool
  const appB = await prisma.application.create({
    data: {
      candidateId: candidates[1].id,
      jobId: job.id,
      status: 'REJECTED',
      stage: 'INTERVIEW',
      screenResult: 'PASS',
      rejectReason: '不匹配',
      rejectToPool: true,
    },
  });
  const interviewB = await prisma.interview.create({
    data: {
      applicationId: appB.id,
      round: 'FIRST',
      roundName: '初试',
      startTime: new Date(Date.now() - 3 * 86400000),
      endTime: new Date(Date.now() - 3 * 86400000 + 3600000),
      method: 'VIDEO',
      meetingLink: 'https://meeting.example.com/b',
      status: 'COMPLETED',
      roundResult: 'REJECT',
      interviewers: { create: [{ userId: interviewer.id }] },
    },
  });
  await prisma.interviewEvaluation.create({
    data: {
      interviewId: interviewB.id,
      interviewerId: interviewer.id,
      scores: JSON.stringify({ professional: 3, experience: 3, problemSolving: 3, communication: 4, motivation: 3, values: 4 }),
      strengths: '沟通表达清晰，学习意愿较强，有一定项目经验可快速上手业务。',
      risks: '技术深度与岗位要求存在差距，复杂场景方案设计经验不足。',
      overall: '整体可作为储备人才，但与当前高级前端岗位匹配度一般，建议进入人才库后续再联系。',
      conclusion: 'NO',
      nextRound: 'NO',
      status: 'SUBMITTED',
      submittedAt: new Date(),
    },
  });

  // C full path - currently at interview ready for offer demo path
  // We'll seed C as onboarded almost complete for demo, plus keep flow data
  const appC = await prisma.application.create({
    data: {
      candidateId: candidates[2].id,
      jobId: job.id,
      status: 'INTERVIEW',
      stage: 'INTERVIEW',
      screenResult: 'PASS',
      deptResult: 'PASS',
      deptComment: '技术背景匹配，建议安排面试',
    },
  });
  await prisma.processEvent.createMany({
    data: [
      { applicationId: appC.id, type: 'ENTER', toStatus: 'HR_SCREEN', operatorName: '李招聘HR' },
      { applicationId: appC.id, type: 'ADVANCE', fromStatus: 'HR_SCREEN', toStatus: 'DEPT_SCREEN', operatorName: '李招聘HR' },
      { applicationId: appC.id, type: 'ADVANCE', fromStatus: 'DEPT_SCREEN', toStatus: 'INTERVIEW', operatorName: '王部门负责人', reason: '技术背景匹配' },
    ],
  });

  const interviewC = await prisma.interview.create({
    data: {
      applicationId: appC.id,
      round: 'FINAL',
      roundName: '终试',
      startTime: new Date(Date.now() + 2 * 86400000),
      endTime: new Date(Date.now() + 2 * 86400000 + 3600000),
      method: 'ONSITE',
      location: '北京总部 3F 会议室A',
      status: 'SCHEDULED',
      noticeContent: `【面试通知】\n候选人：候选C-完整入职\n职位：高级前端工程师\n轮次：终试\n时间：请查系统\n方式：线下面试\n地点：北京总部 3F 会议室A\n面试官：赵面试官`,
      interviewers: { create: [{ userId: interviewer.id }, { userId: deptHead.id }] },
    },
  });

  await prisma.todo.createMany({
    data: [
      {
        userId: hrUser.id,
        type: 'ARRANGE_INTERVIEW',
        title: '跟进终面并准备Offer：候选C-完整入职',
        refType: 'Application',
        refId: appC.id,
      },
      {
        userId: interviewer.id,
        type: 'EVALUATE',
        title: '待评价：候选C-完整入职 终试（面试结束后提交）',
        refType: 'Interview',
        refId: interviewC.id,
        dueAt: interviewC.endTime,
      },
      {
        userId: lead.id,
        type: 'APPROVE_REQUEST',
        title: '查看招聘中需求进度：研发中心高级前端工程师2人',
        refType: 'RecruitRequest',
        refId: request.id,
      },
    ],
  });

  await prisma.activity.createMany({
    data: [
      { type: 'JOB_PUBLISHED', title: '职位已发布：高级前端工程师', jobId: job.id, actorName: '李招聘HR' },
      { type: 'CANDIDATE_ENTER', title: '候选C-完整入职 进入职位 高级前端工程师', jobId: job.id, actorName: '李招聘HR' },
      { type: 'PROCESS_ADVANCE', title: '候选C-完整入职 通过部门筛选', jobId: job.id, actorName: '王部门负责人' },
    ],
  });

  // ===== Phase 2 seed =====
  const evalModel = await prisma.evalModel.create({
    data: {
      name: '前端岗位评价模型',
      jobFamily: '工程-前端',
      dimensions: JSON.stringify([
        { key: 'professional', label: '专业能力', weight: 0.25, anchors: '框架/工程化深度', veto: false },
        { key: 'experience', label: '相关经验', weight: 0.2, anchors: '复杂业务交付', veto: false },
        { key: 'problemSolving', label: '问题解决', weight: 0.2, anchors: '分析与权衡', veto: false },
        { key: 'communication', label: '沟通协作', weight: 0.15, anchors: '跨团队协作', veto: false },
        { key: 'motivation', label: '动机与稳定性', weight: 0.1, anchors: '长期投入', veto: false },
        { key: 'values', label: '价值观风险', weight: 0.1, anchors: '诚信与合规', veto: true },
      ]),
      passScore: 3.5,
    },
  });

  const flowStd = await prisma.flowTemplate.create({
    data: {
      name: '标准社招流程',
      description: 'HR筛选→部门筛选→初试→复试→Offer',
      nodes: {
        create: [
          { key: 'HR_SCREEN', name: 'HR筛选', type: 'SCREEN', sort: 1, role: 'HR', slaHours: 48 },
          { key: 'DEPT_SCREEN', name: '部门筛选', type: 'SCREEN', sort: 2, role: 'DEPT_HEAD', slaHours: 72, skippable: true },
          { key: 'FIRST_INTERVIEW', name: '初试', type: 'INTERVIEW', sort: 3, role: 'INTERVIEWER', slaHours: 120 },
          { key: 'SECOND_INTERVIEW', name: '复试', type: 'INTERVIEW', sort: 4, role: 'INTERVIEWER', slaHours: 120, skippable: true },
          { key: 'OFFER', name: 'Offer', type: 'OFFER', sort: 5, role: 'HR', slaHours: 72 },
        ],
      },
    },
  });

  const flowFast = await prisma.flowTemplate.create({
    data: {
      name: '快速通道流程',
      description: 'HR筛选→终试→Offer（高潜/内推）',
      nodes: {
        create: [
          { key: 'HR_SCREEN', name: 'HR筛选', type: 'SCREEN', sort: 1, role: 'HR', slaHours: 24 },
          { key: 'FINAL_INTERVIEW', name: '终试', type: 'INTERVIEW', sort: 2, role: 'INTERVIEWER', slaHours: 72 },
          { key: 'OFFER', name: 'Offer', type: 'OFFER', sort: 3, role: 'HR', slaHours: 48 },
        ],
      },
    },
  });

  const standard = await prisma.jobStandard.create({
    data: {
      code: 'FE-SENIOR',
      name: '高级前端工程师标准',
      family: '工程-前端',
      version: 1,
      isLatest: true,
      jd: '负责企业级前端系统架构与核心模块交付',
      requirements: '3年以上 React/TypeScript 经验；具备复杂业务系统经验',
      hardCriteria: JSON.stringify([{ key: 'ts', label: 'TypeScript', required: true }]),
      skills: JSON.stringify(['React', 'TypeScript', '工程化']),
      softSkills: JSON.stringify(['沟通协作', '主人翁意识']),
      flowTemplateId: flowStd.id,
      evalModelId: evalModel.id,
      interviewRounds: JSON.stringify(['初试', '复试', '终试']),
    },
  });

  await prisma.job.update({
    where: { id: job.id },
    data: {
      standardId: standard.id,
      standardVersion: 1,
      flowTemplateId: flowStd.id,
      evalModelId: evalModel.id,
    },
  });

  const chBoss = await prisma.channel.create({
    data: {
      name: 'Boss直聘',
      code: 'BOSS',
      type: 'SITE',
      accounts: { create: [{ accountName: '公司主账号', externalId: 'boss-demo-001' }] },
    },
  });
  await prisma.channel.create({
    data: {
      name: '猎聘',
      code: 'LIEPIN',
      type: 'SITE',
      accounts: { create: [{ accountName: '猎聘企业账号', externalId: 'liepin-demo-001' }] },
    },
  });
  await prisma.channel.create({
    data: {
      name: '内推渠道',
      code: 'REFERRAL',
      type: 'REFERRAL',
      accounts: { create: [{ accountName: '内推门户' }] },
    },
  });

  await prisma.jobChannelPublish.create({
    data: {
      jobId: job.id,
      channelId: chBoss.id,
      status: 'PUBLISHED',
      externalRef: `BOSS-${Date.now()}`,
      resultMsg: '种子数据模拟发布成功',
      publishedAt: new Date(),
    },
  });

  await prisma.slaRule.createMany({
    data: [
      { name: '筛选48小时', scope: 'NODE', nodeKey: 'HR_SCREEN', hours: 48, warnHours: 36, escalateRole: 'RECRUIT_LEAD' },
      { name: '评价24小时', scope: 'GLOBAL', nodeKey: 'EVALUATE', hours: 24, warnHours: 12, escalateRole: 'HR' },
    ],
  });

  await prisma.semanticDict.createMany({
    data: [
      { category: 'FIELD', key: 'application.status', label: '应聘状态', definition: '挂在应聘记录上的流程状态，不挂候选人主档' },
      { category: 'METRIC', key: 'funnel.entered', label: '新增简历', definition: '按应聘记录计数，不按候选人主档' },
      { category: 'ACTION', key: 'REJECT_CANDIDATE', label: '淘汰候选人', definition: '高风险动作，须人工确认后执行' },
      { category: 'ACTION', key: 'SEND_OFFER', label: '发送Offer', definition: '高风险动作，须人工确认后执行' },
      { category: 'RULE', key: 'BR-001', label: '状态挂应聘记录', definition: '流程推进必须基于应聘记录' },
      { category: 'ENUM', key: 'offer.status.SENT', label: 'Offer已发送', definition: '审批通过后由HR记录发送结果' },
      { category: 'PERMISSION', key: 'salary.view', label: '查看薪酬', definition: 'DATA_VIEWER/INTERVIEWER默认脱敏' },
    ],
  });

  // Secure link demo for candidate C interview confirm
  const crypto = await import('crypto');
  const portalToken = crypto.randomBytes(16).toString('hex');
  await prisma.secureLink.create({
    data: {
      token: portalToken,
      type: 'INTERVIEW_CONFIRM',
      candidateId: candidates[2].id,
      applicationId: appC.id,
      interviewId: interviewC.id,
      expiresAt: new Date(Date.now() + 7 * 86400000),
    },
  });

  await prisma.interview.update({
    where: { id: interviewC.id },
    data: {
      slotOptions: JSON.stringify([
        { start: new Date(Date.now() + 2 * 86400000).toISOString(), end: new Date(Date.now() + 2 * 86400000 + 3600000).toISOString(), label: '方案A' },
        { start: new Date(Date.now() + 3 * 86400000).toISOString(), end: new Date(Date.now() + 3 * 86400000 + 3600000).toISOString(), label: '方案B' },
      ]),
      packContent: '简历摘要、JD、关注点：工程化与复杂组件设计',
    },
  });

  await prisma.candidate.update({
    where: { id: candidates[1].id },
    data: { poolTier: 'KEY', poolLevel: 'A', poolActiveScore: 80, retainUntil: new Date(Date.now() + 180 * 86400000), privacyConsent: true },
  });

  await prisma.alertSubscription.create({
    data: { userId: hrUser.id, alertType: 'STALL', channel: 'INAPP' },
  });

  console.log('Seed completed.');
  console.log('Demo accounts (password: 123456):');
  console.log('  admin / lead / hr / dept / interviewer / approver / ops / viewer');
  console.log(`Phase2 portal demo: /portal/${portalToken}`);
  console.log(`Flow templates: ${flowStd.name}, ${flowFast.name}`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
