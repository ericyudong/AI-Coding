export const APP_STATUS: Record<string, { text: string; color: string }> = {
  NEW: { text: '新进入', color: 'default' },
  HR_SCREEN: { text: 'HR筛选', color: 'processing' },
  DEPT_SCREEN: { text: '部门筛选', color: 'processing' },
  INTERVIEW: { text: '面试中', color: 'blue' },
  OFFER: { text: 'Offer中', color: 'gold' },
  ONBOARDING: { text: '待入职', color: 'cyan' },
  HIRED: { text: '已入职', color: 'success' },
  REJECTED: { text: '已淘汰', color: 'error' },
  WITHDRAWN: { text: '已放弃', color: 'default' },
  TALENT_POOL: { text: '人才库', color: 'purple' },
};

export const REQUEST_STATUS: Record<string, { text: string; color: string }> = {
  DRAFT: { text: '草稿', color: 'default' },
  PENDING: { text: '审批中', color: 'processing' },
  APPROVED: { text: '已通过', color: 'success' },
  REJECTED: { text: '已驳回', color: 'error' },
  RECRUITING: { text: '招聘中', color: 'blue' },
  COMPLETED: { text: '已完成', color: 'success' },
  CLOSED: { text: '已关闭', color: 'default' },
};

export const JOB_STATUS: Record<string, { text: string; color: string }> = {
  DRAFT: { text: '草稿', color: 'default' },
  OPEN: { text: '招聘中', color: 'success' },
  PAUSED: { text: '暂停', color: 'warning' },
  CLOSED: { text: '已关闭', color: 'default' },
};

export const OFFER_STATUS: Record<string, { text: string; color: string }> = {
  DRAFT: { text: '草稿', color: 'default' },
  PENDING: { text: '审批中', color: 'processing' },
  APPROVED: { text: '已通过', color: 'success' },
  REJECTED: { text: '已驳回', color: 'error' },
  SENT: { text: '已发送', color: 'blue' },
  ACCEPTED: { text: '已接受', color: 'success' },
  DECLINED: { text: '已拒绝', color: 'error' },
  EXPIRED: { text: '已过期', color: 'default' },
  WITHDRAWN: { text: '已撤回', color: 'default' },
};

export const ONBOARD_STATUS: Record<string, { text: string; color: string }> = {
  PENDING_CONFIRM: { text: '待确认', color: 'processing' },
  CONFIRMED: { text: '已确认', color: 'blue' },
  DELAYED: { text: '延期', color: 'warning' },
  HIRED: { text: '已入职', color: 'success' },
  ABANDONED: { text: '放弃', color: 'error' },
};

export const TODO_TYPE: Record<string, string> = {
  APPROVE_REQUEST: '待审批需求',
  SCREEN: '待筛选',
  ARRANGE_INTERVIEW: '待安排面试',
  EVALUATE: '待评价',
  APPROVE_OFFER: '待审批Offer',
  ONBOARDING: '待入职跟进',
};

export function canRole(role: string, ...roles: string[]) {
  return role === 'ADMIN' || roles.includes(role);
}
