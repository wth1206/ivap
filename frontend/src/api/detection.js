import http from './http'

export function predictImage(formData) {
  return http.post('/detection/predict', formData, { timeout: 300000 })
}

export function listTasks(params = {}) {
  return http.get('/detection/tasks', { params })
}

export function getTask(taskId, config = {}) {
  return http.get(`/detection/tasks/${taskId}`, config)
}

export function deleteTask(taskId) {
  return http.delete(`/detection/tasks/${taskId}`)
}

export function getModels() {
  return http.get('/detection/models')
}

export function getOverview() {
  return http.get('/detection/overview')
}
