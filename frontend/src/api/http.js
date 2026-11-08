import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 180000,
})

http.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const payload = error.response?.data?.error
    const message = payload?.message || error.message || '请求失败'
    const code = payload?.code
    const requestId = payload?.request_id

    if (!error.config?.skipErrorToast && error.code !== 'ERR_CANCELED') {
      const suffix = requestId ? `（request_id: ${requestId.slice(0, 8)}…）` : ''
      ElMessage.error(`${message}${suffix}`)
    }

    return Promise.reject({
      ...error,
      message,
      code,
      requestId,
      status: error.response?.status,
    })
  },
)

export default http
