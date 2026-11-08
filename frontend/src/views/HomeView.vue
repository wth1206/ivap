<template>
  <div class="page">
    <PageHeader
      title="系统首页"
      description="ECE-YOLO 目标检测 · 统计事实 · LLM 分析 · RAG 知识库 · Agent 编排"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="refresh">刷新数据</el-button>
        <el-button type="primary" :icon="Aim" @click="$router.push('/detect')">开始检测</el-button>
      </template>
    </PageHeader>

    <div class="stat-grid">
      <StatCard label="检测任务" :value="formatNumber(overview?.total_tasks)" hint="历史累计" tone="blue" :icon="DataLine" />
      <StatCard label="检测目标" :value="formatNumber(overview?.total_objects)" hint="全部任务合计" tone="green" :icon="Aim" />
      <StatCard label="知识文档" :value="formatNumber(app.vectorStore?.documents)" hint="已索引文档" tone="violet" :icon="Collection" />
      <StatCard label="知识向量" :value="formatNumber(app.vectorStore?.vectors)" hint="FAISS 向量数" tone="amber" :icon="Connection" />
    </div>

    <div class="grid-2">
      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>类别分布</strong>
              <span>来自全部检测任务的目标统计</span>
            </div>
            <el-tag effect="light" size="small">{{ Object.keys(classStatistics).length }} 类</el-tag>
          </div>
        </template>
        <ClassBarChart :data="classStatistics" :height="280" />
      </el-card>

      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>运行状态</strong>
              <span>后端组件实时探针</span>
            </div>
            <el-tag :type="app.healthTag" effect="light" size="small">{{ app.healthText }}</el-tag>
          </div>
        </template>
        <div class="health-list">
          <div class="health-row">
            <span>数据库</span>
            <el-tag size="small" :type="app.database?.status === 'ok' ? 'success' : 'danger'" effect="light">
              {{ app.database?.status || 'unknown' }}
            </el-tag>
          </div>
          <div class="health-row">
            <span>ECE-YOLO</span>
            <div class="health-value">
              <el-tag size="small" :type="app.detector?.status === 'ok' ? 'success' : 'warning'" effect="light">
                {{ app.detector?.status || 'unknown' }}
              </el-tag>
              <small>{{ app.detector?.device || '未加载' }}</small>
            </div>
          </div>
          <div class="health-row">
            <span>LLM</span>
            <div class="health-value">
              <el-tag size="small" :type="app.llm?.configured ? 'success' : 'info'" effect="light">
                {{ app.llm?.configured ? '已配置' : '未配置' }}
              </el-tag>
              <small>{{ app.llm?.model || '—' }}</small>
            </div>
          </div>
          <div class="health-row">
            <span>知识库</span>
            <div class="health-value">
              <el-tag size="small" :type="app.vectorStore?.status === 'ok' ? 'success' : 'warning'" effect="light">
                {{ app.vectorStore?.status || 'unknown' }}
              </el-tag>
              <small>{{ app.vectorStore?.embedding_model || '—' }}</small>
            </div>
          </div>
        </div>
        <div class="quick-actions">
          <el-button @click="$router.push('/knowledge')">知识库</el-button>
          <el-button @click="$router.push('/agent')">Agent 对话</el-button>
          <el-button @click="$router.push('/history')">历史任务</el-button>
        </div>
      </el-card>
    </div>

    <el-card class="panel" shadow="never">
      <template #header>
        <div class="panel-head">
          <div>
            <strong>最近检测任务</strong>
            <span>按创建时间倒序</span>
          </div>
          <el-button text type="primary" @click="$router.push('/history')">查看全部</el-button>
        </div>
      </template>
      <TaskTable :tasks="recentTasks" :loading="loadingTasks" :show-actions="false" />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { Aim, Collection, Connection, DataLine, Refresh } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatCard from '@/components/StatCard.vue'
import ClassBarChart from '@/components/ClassBarChart.vue'
import TaskTable from '@/components/TaskTable.vue'
import { useAppStore } from '@/stores/app'
import { useDetectionStore } from '@/stores/detection'
import { listTasks } from '@/api/detection'
import { formatNumber } from '@/utils/format'

const app = useAppStore()
const detection = useDetectionStore()
const loading = ref(false)
const loadingTasks = ref(false)
const recentTasks = ref([])

const overview = computed(() => detection.overview)
const classStatistics = computed(() => overview.value?.class_statistics || {})

async function refresh() {
  loading.value = true
  loadingTasks.value = true
  try {
    await Promise.allSettled([
      app.fetchHealth(),
      detection.loadOverview(),
      listTasks({ page: 1, page_size: 5 }).then((data) => {
        recentTasks.value = data.items || []
      }),
    ])
  } finally {
    loading.value = false
    loadingTasks.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.grid-2 {
  display: grid;
  grid-template-columns: 1.25fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.health-list {
  display: grid;
  gap: 12px;
}
.health-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  border-bottom: 1px dashed #eef2f7;
  color: #475569;
  font-size: 13px;
}
.health-value {
  display: flex;
  align-items: center;
  gap: 8px;
}
.health-value small {
  color: #94a3b8;
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.quick-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
@media (max-width: 1200px) {
  .stat-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
