<template>
  <div class="page">
    <PageHeader
      title="智能分析"
      description="Python 统计事实，LLM 只负责组织语言；报告包含 8 个固定章节。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loadingTasks" @click="loadTasks">刷新任务</el-button>
      </template>
    </PageHeader>

    <el-card class="panel select-panel" shadow="never">
      <div class="select-row">
        <div class="select-copy">
          <strong>选择检测任务</strong>
          <span>仅展示已完成（success）的任务</span>
        </div>
        <el-select
          v-model="selectedTaskId"
          filterable
          clearable
          placeholder="请选择任务"
          style="width: 360px"
          :loading="loadingTasks"
        >
          <el-option
            v-for="item in tasks"
            :key="item.task_id"
            :label="`${item.image_name} · ${item.total_objects} 个目标 · ${formatDate(item.created_at)}`"
            :value="item.task_id"
          />
        </el-select>
        <el-button type="primary" :disabled="!selectedTaskId" :loading="generating" @click="generate(true)">
          {{ report ? '重新生成' : '生成报告' }}
        </el-button>
      </div>
    </el-card>

    <template v-if="selectedTask">
      <el-card class="panel" shadow="never">
        <div class="task-summary">
          <div class="task-thumb">
            <el-image v-if="selectedTask.image_url" :src="selectedTask.image_url" fit="cover" />
          </div>
          <div class="task-copy">
            <div class="task-title">
              <strong>{{ selectedTask.image_name }}</strong>
              <StatusTag :status="selectedTask.status" />
              <el-tag v-if="selectedTask.is_mock" type="warning" effect="light">Mock</el-tag>
            </div>
            <div class="task-meta">
              <span>{{ selectedTask.model_name }}</span>
              <span>{{ selectedTask.total_objects }} 个目标</span>
              <span>{{ selectedTask.inference_time_ms }} ms</span>
              <span>{{ formatDate(selectedTask.created_at) }}</span>
            </div>
            <el-button link type="primary" @click="$router.push('/detect')">查看检测结果</el-button>
          </div>
        </div>
      </el-card>

      <el-card class="panel report-panel" shadow="never" v-loading="generating || loadingReport">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>分析报告</strong>
              <span v-if="report">
                {{ report.model_name }} · {{ report.latency_ms }} ms ·
                {{ report.usage.prompt_tokens }}+{{ report.usage.completion_tokens }} tokens
              </span>
              <span v-else>尚未生成</span>
            </div>
            <div class="report-actions">
              <el-tag v-if="report?.is_mock" type="warning" effect="light">Mock 报告</el-tag>
              <el-tag v-if="report" type="info" effect="light">{{ report.prompt_version }}</el-tag>
              <el-button v-if="report" size="small" :icon="CopyDocument" @click="copyReport">复制 Markdown</el-button>
              <el-button v-if="report" size="small" type="primary" plain :loading="generating" @click="generate(true)">
                重新生成
              </el-button>
            </div>
          </div>
        </template>

        <el-alert
          v-if="report?.is_mock"
          title="当前为 Mock 报告，未调用真实 LLM，不能作为真实分析结论。"
          type="warning"
          :closable="false"
          show-icon
          class="mock-alert"
        />

        <div v-if="report" class="report-body">
          <MarkdownView :content="report.content" />
          <div class="report-footer">
            <span>报告 ID：{{ report.report_id }}</span>
            <span>生成时间：{{ formatDate(report.created_at) }}</span>
          </div>
        </div>
        <EmptyState
          v-else-if="!generating && !loadingReport"
          title="该任务还没有分析报告"
          description="点击“生成报告”，系统会先计算统计事实，再调用 LLM 生成 8 段分析。"
        >
          <template #action>
            <el-button type="primary" :loading="generating" @click="generate(false)">生成报告</el-button>
          </template>
        </EmptyState>
      </el-card>
    </template>

    <el-card v-else class="panel empty-panel" shadow="never">
      <EmptyState
        title="请选择一个检测任务"
        description="从上方下拉框选择已完成的任务，或先在图像检测页面完成一次检测。"
      >
        <template #action>
          <el-button type="primary" @click="$router.push('/detect')">去检测</el-button>
        </template>
      </EmptyState>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CopyDocument, Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatusTag from '@/components/StatusTag.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import EmptyState from '@/components/EmptyState.vue'
import { listTasks } from '@/api/detection'
import { generateReport, getReport } from '@/api/analysis'
import { formatDate } from '@/utils/format'

const route = useRoute()
const router = useRouter()
const tasks = ref([])
const selectedTaskId = ref(route.query.task_id || '')
const report = ref(null)
const loadingTasks = ref(false)
const loadingReport = ref(false)
const generating = ref(false)

const selectedTask = computed(() => tasks.value.find((item) => item.task_id === selectedTaskId.value) || null)

async function loadTasks() {
  loadingTasks.value = true
  try {
    const data = await listTasks({ page: 1, page_size: 100, status: 'success' })
    tasks.value = data.items || []
    if (!selectedTaskId.value && tasks.value.length) {
      selectedTaskId.value = tasks.value[0].task_id
    }
  } finally {
    loadingTasks.value = false
  }
}

async function loadReport() {
  if (!selectedTaskId.value) {
    report.value = null
    return
  }
  loadingReport.value = true
  try {
    report.value = await getReport(selectedTaskId.value)
  } catch (error) {
    if (error.code === 'ANALYSIS_NOT_FOUND') {
      report.value = null
    } else {
      report.value = null
      ElMessage.error(error.message || '报告加载失败')
    }
  } finally {
    loadingReport.value = false
  }
}

async function generate(force) {
  if (!selectedTaskId.value) return
  generating.value = true
  try {
    report.value = await generateReport(selectedTaskId.value, force)
    ElMessage.success('分析报告已生成')
  } finally {
    generating.value = false
  }
}

async function copyReport() {
  if (!report.value) return
  await navigator.clipboard.writeText(report.value.content)
  ElMessage.success('Markdown 已复制')
}

watch(selectedTaskId, (value) => {
  router.replace({ path: '/analysis', query: value ? { task_id: value } : {} })
  loadReport()
})

onMounted(async () => {
  await loadTasks()
  await loadReport()
})
</script>

<style scoped>
.select-panel {
  margin-bottom: 16px;
}
.select-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.select-copy {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-right: auto;
}
.select-copy strong {
  font-size: 14px;
  color: #1e293b;
}
.select-copy span {
  font-size: 11px;
  color: #94a3b8;
}
.task-summary {
  display: flex;
  align-items: center;
  gap: 16px;
}
.task-thumb {
  width: 120px;
  height: 76px;
  border-radius: 10px;
  overflow: hidden;
  background: #f1f5f9;
  flex: none;
}
.task-thumb :deep(img) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.task-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.task-title strong {
  font-size: 15px;
  color: #0f172a;
}
.task-meta {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  color: #64748b;
  font-size: 12px;
}
.report-panel {
  margin-top: 16px;
}
.report-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.report-body {
  padding: 4px 2px;
}
.report-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 18px;
  padding-top: 12px;
  border-top: 1px dashed #eef2f7;
  color: #94a3b8;
  font-size: 11px;
}
.mock-alert {
  margin-bottom: 12px;
}
.empty-panel {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
