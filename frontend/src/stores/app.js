import { defineStore } from 'pinia'
import http from '@/api/http'

export const useAppStore = defineStore('app', {
  state: () => ({
    health: null,
    loading: false,
    timer: null,
  }),
  getters: {
    detector(state) {
      return state.health?.components?.detector || null
    },
    database(state) {
      return state.health?.components?.database || null
    },
    llm(state) {
      return state.health?.components?.llm || null
    },
    vectorStore(state) {
      return state.health?.components?.vector_store || null
    },
    healthTag(state) {
      if (!state.health) return 'info'
      return state.health.status === 'ok' ? 'success' : 'warning'
    },
    healthText(state) {
      if (!state.health) return '状态未知'
      return state.health.status === 'ok' ? '系统正常' : '系统降级'
    },
  },
  actions: {
    async fetchHealth() {
      this.loading = true
      try {
        this.health = await http.get('/health', { skipErrorToast: true })
      } catch {
        this.health = null
      } finally {
        this.loading = false
      }
    },
    startPolling() {
      this.stopPolling()
      this.timer = window.setInterval(() => this.fetchHealth(), 30000)
    },
    stopPolling() {
      if (this.timer) {
        window.clearInterval(this.timer)
        this.timer = null
      }
    },
  },
})
