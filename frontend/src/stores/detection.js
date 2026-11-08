import { defineStore } from 'pinia'
import { getModels, getOverview } from '@/api/detection'

export const useDetectionStore = defineStore('detection', {
  state: () => ({
    models: [],
    defaultModel: null,
    overview: null,
    loadingModels: false,
  }),
  getters: {
    availableModels(state) {
      return state.models.filter((item) => item.available)
    },
    realModels(state) {
      return state.models.filter((item) => !item.is_mock)
    },
  },
  actions: {
    async loadModels() {
      this.loadingModels = true
      try {
        const data = await getModels()
        this.models = data.models || []
        this.defaultModel = data.default_model || this.models[0]?.key || null
      } finally {
        this.loadingModels = false
      }
    },
    async loadOverview() {
      this.overview = await getOverview()
    },
  },
})
