export interface NavItem {
  label: string
  icon: string
  route?: string
  feature?: string
  children?: { label: string; route: string; feature?: string; reserved?: boolean }[]
}

/** α版本侧边栏：知识资产 / 合同 / 履约 / 商业模式(预留) / 系统管理 */
export const SIDEBAR_NAV: NavItem[] = [
  {
    label: '知识资产AI',
    icon: 'knowledge',
    children: [
      { label: '企业知识问答', route: '/knowledge', feature: 'knowledge' },
      { label: '合同库', route: '/cms/ledger', feature: 'contract_search' },
    ],
  },
  {
    label: '合同AI',
    icon: 'contract',
    children: [
      { label: '合同导入与解析', route: '/cms/import', feature: 'contract_import' },
      { label: '合同列表', route: '/cms/ledger', feature: 'contract_detail' },
      { label: '企业合同搜索', route: '/cms/search', feature: 'contract_search' },
      { label: '版本对比', route: '/cms/compare', feature: 'contract_detail' },
      { label: '合同起草审核', route: '/contract/draft', reserved: true },
    ],
  },
  {
    label: '履约AI',
    icon: 'performance',
    children: [
      { label: '履约总览', route: '/performance', feature: 'performance' },
      { label: '履约助手', route: '/performance/assistant', feature: 'performance' },
      { label: '供应商中心', route: '/performance/suppliers', feature: 'supplier' },
      { label: '客户中心', route: '/performance/customers', feature: 'customer' },
      { label: 'ERP订单同步', route: '/performance/orders', feature: 'customer' },
    ],
  },
  {
    label: '商业模式AI',
    icon: 'business',
    children: [{ label: '功能开发中', route: '/business-model', reserved: true }],
  },
  {
    label: '系统管理',
    icon: 'admin',
    children: [
      { label: '用户管理', route: '/admin/users', feature: 'system_admin' },
      { label: '角色权限', route: '/admin/roles', feature: 'system_admin' },
      { label: '标签体系', route: '/admin/tags', feature: 'system_admin' },
    ],
  },
]
