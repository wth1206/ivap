export function formatDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '0'
  return Number(value).toLocaleString('zh-CN')
}

export function stripStatic(url) {
  if (!url) return ''
  return url.startsWith('/static/') ? url.slice('/static/'.length) : url
}

export const statusMap = {
  pending: { text: '待检测', type: 'info' },
  running: { text: '检测中', type: 'warning' },
  success: { text: '已完成', type: 'success' },
  failed: { text: '失败', type: 'danger' },
  processing: { text: '索引中', type: 'warning' },
  ready: { text: '就绪', type: 'success' },
}

export function statusText(status) {
  return statusMap[status]?.text || status || '-'
}

export function statusType(status) {
  return statusMap[status]?.type || 'info'
}

export function shortId(value, length = 8) {
  if (!value) return '-'
  return value.length > length ? `${value.slice(0, length)}…` : value
}
