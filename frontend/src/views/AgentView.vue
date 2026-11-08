<template>
  <div class="page">
    <PageHeader
      title="Agent 对话"
      description="LangGraph 自动调用检测、任务查询、统计、RAG 与报告工具；工具轨迹和引用可追溯。"
    >
      <template #actions>
        <el-button :icon="Plus" @click="newConversation">新对话</el-button>
      </template>
    </PageHeader>

    <div class="agent-layout">
      <el-card class="panel conversation-panel" shadow="never">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>会话</strong>
              <span>{{ chat.conversations.length }} 个</span>
            </div>
            <el-button text :icon="Refresh" :loading="chat.loadingConversations" @click="chat.loadConversations()" />
          </div>
        </template>
        <div class="conversation-list">
          <button
            v-for="item in chat.conversations"
            :key="item.conversation_id"
            class="conversation-item"
            :class="{ active: item.conversation_id === chat.currentId }"
            @click="openConversation(item.conversation_id)"
          >
            <strong>{{ item.title }}</strong>
            <span>{{ item.last_message || '暂无消息' }}</span>
            <small>{{ formatDate(item.updated_at) }}</small>
          </button>
          <EmptyState v-if="!chat.conversations.length" title="还没有会话" description="发送第一条消息开始对话。" />
        </div>
      </el-card>

      <el-card class="panel chat-panel" shadow="never">
        <template #header>
          <div class="chat-head">
            <div class="chat-title">
              <strong>{{ currentTitle }}</strong>
              <span>ECE-YOLO · RAG · LLM</span>
            </div>
            <div class="chat-tools">
              <el-select
                v-model="selectedTaskId"
                clearable
                filterable
                placeholder="关联检测任务（可选）"
                style="width: 240px"
                :loading="loadingTasks"
              >
                <el-option
                  v-for="item in taskOptions"
                  :key="item.task_id"
                  :label="`${item.image_name} · ${item.total_objects} 目标`"
                  :value="item.task_id"
                />
              </el-select>
              <el-tag v-if="imagePath" type="success" effect="light" size="small">已关联图片</el-tag>
            </div>
          </div>
        </template>

        <div ref="messagesRef" class="messages" v-loading="chat.loadingMessages">
          <div v-if="!chat.messages.length && !sending" class="chat-empty">
            <div class="chat-empty-icon"><el-icon :size="28"><ChatDotRound /></el-icon></div>
            <h3>今天想分析什么？</h3>
            <p>试试：统计最近任务、查询某次检测结果、解释小目标检测难点、为任务生成分析报告。</p>
            <div class="suggestions">
              <el-button v-for="text in suggestions" :key="text" size="small" plain @click="useSuggestion(text)">
                {{ text }}
              </el-button>
            </div>
          </div>

          <div
            v-for="(message, index) in chat.messages"
            :key="`${message.message_id || 'new'}-${index}`"
            class="message-row"
            :class="message.role"
          >
            <div class="avatar" :class="message.role">
              <el-icon><UserFilled v-if="message.role === 'user'" /><MagicStick v-else /></el-icon>
            </div>
            <div class="bubble-wrap">
              <div class="bubble">
                <MarkdownView v-if="message.role === 'assistant'" :content="message.content" />
                <p v-else class="user-text">{{ message.content }}</p>
              </div>
              <ToolCallList v-if="message.tool_calls?.length" :calls="message.tool_calls" />
              <CitationList v-if="message.citations?.length" :citations="message.citations" />
              <div v-if="message.role === 'assistant'" class="message-meta">
                <el-tag v-if="message.is_mock" type="warning" effect="light" size="small">Mock</el-tag>
                <span v-if="message.created_at">{{ formatDate(message.created_at) }}</span>
              </div>
            </div>
          </div>

          <div v-if="sending" class="message-row assistant">
            <div class="avatar assistant"><el-icon><MagicStick /></el-icon></div>
            <div class="bubble-wrap">
              <div class="bubble typing"><span /><span /><span /></div>
            </div>
          </div>
        </div>

        <div class="composer">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            resize="none"
            placeholder="输入自然语言指令，Enter 发送，Shift+Enter 换行"
            :disabled="sending"
            @keydown.enter.exact.prevent="send"
          />
          <div class="composer-footer">
            <span class="composer-hint">
              {{ selectedTask ? `当前任务：${selectedTask.image_name} · ${selectedTask.total_objects} 个目标` : '未关联任务，Agent 可能会先询问任务 ID' }}
            </span>
            <el-button type="primary" :icon="Promotion" :loading="sending" :disabled="!input.trim()" @click="send">
              发送
            </el-button>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  MagicStick,
  Plus,
  Promotion,
  Refresh,
  UserFilled,
} from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import CitationList from '@/components/CitationList.vue'
import ToolCallList from '@/components/ToolCallList.vue'
import EmptyState from '@/components/EmptyState.vue'
import { listTasks, getTask } from '@/api/detection'
import { sendMessage } from '@/api/chat'
import { useChatStore } from '@/stores/chat'
import { formatDate, stripStatic } from '@/utils/format'

const route = useRoute()
const chat = useChatStore()
const input = ref('')
const sending = ref(false)
const messagesRef = ref(null)
const taskOptions = ref([])
const selectedTaskId = ref('')
const selectedTask = ref(null)
const imagePath = ref('')
const loadingTasks = ref(false)

const suggestions = [
  '统计最近 7 天的检测任务',
  'VisDrone 数据集包含哪些类别？',
  '为这个任务生成分析报告',
]

const currentTitle = computed(() => {
  return chat.currentId
    ? chat.conversations.find((item) => item.conversation_id === chat.currentId)?.title || '当前会话'
    : '新会话'
})

async function loadTasks() {
  loadingTasks.value = true
  try {
    const data = await listTasks({ page: 1, page_size: 100 })
    taskOptions.value = data.items || []
  } finally {
    loadingTasks.value = false
  }
}

async function applyTask(taskId) {
  if (!taskId) {
    selectedTask.value = null
    imagePath.value = ''
    return
  }
  const fromList = taskOptions.value.find((item) => item.task_id === taskId)
  selectedTask.value = fromList || null
  try {
    const detail = await getTask(taskId, { skipErrorToast: true })
    selectedTask.value = detail
    imagePath.value = stripStatic(detail.image_url)
  } catch {
    imagePath.value = ''
  }
}

async function openConversation(conversationId) {
  await chat.openConversation(conversationId)
  scrollToBottom()
}

function newConversation() {
  chat.resetConversation()
  input.value = ''
}

function useSuggestion(text) {
  input.value = text
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || sending.value) return
  chat.appendMessage({ role: 'user', content: text, created_at: new Date().toISOString() })
  input.value = ''
  sending.value = true
  scrollToBottom()
  try {
    const result = await sendMessage({
      message: text,
      conversation_id: chat.currentId,
      task_id: selectedTaskId.value || null,
      image_path: imagePath.value || null,
    })
    chat.currentId = result.conversation_id
    chat.appendMessage({
      role: 'assistant',
      message_id: result.message_id,
      content: result.answer,
      tool_calls: result.tool_calls,
      citations: result.citations,
      is_mock: result.is_mock,
      created_at: result.created_at,
    })
    await chat.loadConversations()
    scrollToBottom()
  } finally {
    sending.value = false
  }
}

watch(selectedTaskId, (value) => applyTask(value))

onMounted(async () => {
  await Promise.allSettled([chat.loadConversations(), loadTasks()])
  if (route.query.task_id) {
    selectedTaskId.value = String(route.query.task_id)
  }
  scrollToBottom()
})
</script>

<style scoped>
.agent-layout {
  display: grid;
  grid-template-columns: 270px minmax(0, 1fr);
  gap: 16px;
  height: calc(100vh - 158px);
  min-height: 520px;
}
.conversation-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  max-height: calc(100vh - 250px);
}
.conversation-item {
  border: 1px solid transparent;
  background: transparent;
  border-radius: 10px;
  padding: 10px 12px;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 3px;
  cursor: pointer;
  font-family: inherit;
}
.conversation-item:hover {
  background: #f8fafc;
}
.conversation-item.active {
  background: #eff6ff;
  border-color: #bfdbfe;
}
.conversation-item strong {
  color: #1e293b;
  font-size: 12.5px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conversation-item span {
  color: #94a3b8;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conversation-item small {
  color: #cbd5e1;
  font-size: 10px;
}
.chat-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.chat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.chat-title {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.chat-title strong {
  font-size: 14px;
  color: #0f172a;
}
.chat-title span {
  font-size: 10px;
  color: #94a3b8;
}
.chat-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px 6px 14px;
  min-height: 300px;
}
.chat-empty {
  max-width: 560px;
  margin: 60px auto 0;
  text-align: center;
  color: #64748b;
}
.chat-empty-icon {
  width: 58px;
  height: 58px;
  border-radius: 18px;
  background: #eff6ff;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 14px;
}
.chat-empty h3 {
  margin: 0 0 6px;
  color: #1e293b;
  font-size: 18px;
}
.chat-empty p {
  margin: 0 0 16px;
  font-size: 12.5px;
  line-height: 1.7;
}
.suggestions {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
}
.message-row {
  display: flex;
  gap: 10px;
  margin: 14px 0;
}
.message-row.user {
  flex-direction: row-reverse;
}
.avatar {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
.avatar.user {
  background: #e8f0ff;
  color: #2563eb;
}
.avatar.assistant {
  background: #f1f5f9;
  color: #475569;
}
.bubble-wrap {
  max-width: min(760px, 82%);
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bubble {
  border-radius: 12px;
  padding: 12px 14px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
}
.message-row.user .bubble {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.user-text {
  margin: 0;
  white-space: pre-wrap;
  font-size: 13.5px;
  line-height: 1.65;
}
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  font-size: 10px;
}
.typing {
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 16px;
}
.typing span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #94a3b8;
  animation: blink 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: 0.2s; }
.typing span:nth-child(3) { animation-delay: 0.4s; }
@keyframes blink {
  0%, 80%, 100% { opacity: 0.3; }
  40% { opacity: 1; }
}
.composer {
  border-top: 1px solid #eef2f7;
  padding-top: 12px;
}
.composer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
}
.composer-hint {
  color: #94a3b8;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 1100px) {
  .agent-layout { grid-template-columns: 1fr; height: auto; }
  .conversation-panel { max-height: 220px; }
  .conversation-list { max-height: 160px; }
  .bubble-wrap { max-width: 90%; }
}
</style>
