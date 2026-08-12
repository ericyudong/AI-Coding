export function tagClass(tag: string): string {
  if (tag.includes('高风险') || tag.includes('🔴')) return 'cms-tag-red'
  if (tag.includes('中风险') || tag.includes('🟡')) return 'cms-tag-yellow'
  if (tag.includes('低风险') || tag.includes('🟢')) return 'cms-tag-green'
  if (tag.includes('保密') || tag.includes('自动续签')) return 'cms-tag-purple'
  if (tag.includes('到期')) return 'cms-tag-cyan'
  if (tag.includes('金额') || tag.includes('100万')) return 'cms-tag-yellow'
  if (tag.includes('归档')) return 'cms-tag-gray'
  return 'cms-tag-blue'
}

export function statusClass(status: string): string {
  const map: Record<string, string> = {
    active: 'active',
    pending_sign: 'pending',
    expired: 'expired',
    archived: 'archived',
    terminated: 'expired',
  }
  return map[status] || 'active'
}
