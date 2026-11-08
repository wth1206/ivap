import { defineStore } from 'pinia'
import { listDocuments } from '@/api/knowledge'

export const useKnowledgeStore = defineStore('knowledge', {
  state: () => ({
    documents: [],
    total: 0,
    loading: false,
    page: 1,
    pageSize: 20,
  }),
  actions: {
    async loadDocuments(params = {}) {
      this.loading = true
      try {
        const data = await listDocuments({
          page: this.page,
          page_size: this.pageSize,
          ...params,
        })
        this.documents = data.items || []
        this.total = data.total || 0
      } finally {
        this.loading = false
      }
    },
  },
})
