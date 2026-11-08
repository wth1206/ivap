import http from './http'

export function generateReport(taskId, force = false) {
  return http.post(`/analysis/${taskId}`, { force }, { timeout: 300000 })
}

export function getReport(taskId) {
  return http.get(`/analysis/${taskId}`, { skipErrorToast: true })
}
