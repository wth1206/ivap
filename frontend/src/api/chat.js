import http from './http'

export function sendMessage(payload) {
  return http.post('/chat', payload, { timeout: 300000 })
}

export function getChatHistory(params = {}) {
  return http.get('/chat/history', { params })
}
