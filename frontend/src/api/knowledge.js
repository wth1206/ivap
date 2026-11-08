import http from './http'

export function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  return http.post('/knowledge/upload', form, { timeout: 300000 })
}

export function listDocuments(params = {}) {
  return http.get('/knowledge/documents', { params })
}

export function deleteDocument(documentId) {
  return http.delete(`/knowledge/documents/${documentId}`)
}

export function searchKnowledge(payload) {
  return http.post('/knowledge/search', payload, { timeout: 120000 })
}

export function askKnowledge(payload) {
  return http.post('/knowledge/ask', payload, { timeout: 300000 })
}
