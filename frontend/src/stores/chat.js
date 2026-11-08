import { defineStore } from 'pinia'
import { getChatHistory } from '@/api/chat'

export const useChatStore = defineStore('chat', {
  state: () => ({
    conversations: [],
    currentId: null,
    messages: [],
    loadingConversations: false,
    loadingMessages: false,
  }),
  actions: {
    async loadConversations() {
      this.loadingConversations = true
      try {
        const data = await getChatHistory()
        this.conversations = data.items || []
      } finally {
        this.loadingConversations = false
      }
    },
    async openConversation(conversationId) {
      this.loadingMessages = true
      this.currentId = conversationId
      try {
        const data = await getChatHistory({ conversation_id: conversationId })
        this.messages = data.items || []
      } finally {
        this.loadingMessages = false
      }
    },
    resetConversation() {
      this.currentId = null
      this.messages = []
    },
    appendMessage(message) {
      this.messages.push(message)
    },
  },
})
