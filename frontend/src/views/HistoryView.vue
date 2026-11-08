<template>
  <div class="page">
    <PageHeader
      title="历史任务"
      description="查询、筛选、查看检测详情，删除任务及其图片。"
    >
      <template #actions>
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button type="primary" :icon="Aim" @click="$router.push('/detect')">新建检测</el-button>
      </template>
    </PageHeader>

    <el-card class="panel" shadow="never">
      <div class="filters">
        <el-input
          v-model="filters.keyword"
          placeholder="按图片名称搜索"
          clearable
          style="width: 240px"
          :prefix-icon="Search"
          @keyup.enter="applyFilters"
        />
        <el-select v-model="filters.status" placeholder="全部状态" clearable style="width: 150px">
          <el-option label="待检测" value="pending" />
          <el-option label="检测中" value="running" />
          <el-option label="已完成" value="success" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button type="primary" @click="applyFilters">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <span class="filter-count">共 {{ total }} 条任务</span>
      </div>

      <TaskTable
        :tasks="tasks"
        :loading="loading"
        @view="openDetail"
        @analyze="goAnalysis"
        @delete="removeTask"
      />

      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="load"
        />
      </div>
    </el-card>

    <el-drawer v-model="drawer" title="检测任务详情" size="72%" destroy-on-close>
      <div v-if="detail" class="detail" v-loading="detailLoading">
        <div class="detail-head">
          <div>
            <h3>{{ detail.image_name }}</h3>
            <p>
              {{ detail.model_name }} · {{ detail.width }}×{{ detail.height }} ·
              {{ formatDate(detail.created_at) }}
            </p>
          </div>
          <div class="detail-actions">
            <StatusTag :status="detail.status" />
            <el-button size="small" @click="goAnalysis(detail)">生成分析</el-button>
            <el-button size="small" type="danger" plain @click="removeTask(detail)">删除</el-button>
          </div>
        </div>

        <DetectionViewer
          :image-url="detail.image_url"
          :result-url="detail.result_image"
          :detections="detail.detections || []"
        />

        <div class="detail-grid">
          <div>
            <h4>类别统计</h4>
            <ClassBarChart :data="detail.class_statistics || {}" :height="220" />
          </div>
          <div>
            <h4>任务信息</h4>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="任务 ID">{{ detail.task_id }}</el-descriptions-item>
              <el-descriptions-item label="目标总数">{{ detail.total_objects }}</el-descriptions-item>
              <el-descriptions-item label="推理耗时">{{ detail.inference_time_ms }} ms</el-descriptions-item>
              <el-descriptions-item label="conf / iou">{{ detail.conf_threshold }} / {{ detail.iou_threshold }}</el-descriptions-item>
              <el-descriptions-item label="报告">{{ detail.report_available ? '已有' : '暂无' }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </div>

        <h4>目标明细 <small>{{ detail.detections?.length || 0 }} 条</small></h4>
        <el-table :data="detail.detections || []" size="small" max-height="320">
          <el-table-column type="index" width="50" />
          <el-table-column prop="class_name" label="类别" width="110" />
          <el-table-column label="置信度" width="100">
            <template #default="{ row }">{{ (row.confidence * 100).toFixed(1) }}%</template>
          </el-table-column>
          <el-table-column label="bbox (x1, y1, x2, y2)" min-width="180">
            <template #default="{ row }">{{ row.bbox.join(', ') }}</template>
          </el-table-column>
        </el-table>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Aim, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import TaskTable from '@/components/TaskTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import DetectionViewer from '@/components/DetectionViewer.vue'
import ClassBarChart from '@/components/ClassBarChart.vue'
import { deleteTask, getTask, listTasks } from '@/api/detection'
import { formatDate } from '@/utils/format'

const router = useRouter()
const filters = reactive({ keyword: '', status: '' })
const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const drawer = ref(false)
const detail = ref(null)
const detailLoading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await listTasks({
      page: page.value,
      page_size: pageSize,
      keyword: filters.keyword || undefined,
      status: filters.status || undefined,
    })
    tasks.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  load()
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  applyFilters()
}

async function openDetail(row) {
  drawer.value = true
  detail.value = null
  detailLoading.value = true
  try {
    detail.value = await getTask(row.task_id)
  } finally {
    detailLoading.value = false
  }
}

function goAnalysis(row) {
  router.push({ path: '/analysis', query: { task_id: row.task_id } })
}

async function removeTask(row) {
  try {
    await ElMessageBox.confirm(`确定删除任务 ${row.task_id} 及其图片吗？`, '删除任务', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteTask(row.task_id)
  ElMessage.success('任务已删除')
  if (detail.value?.task_id === row.task_id) drawer.value = false
  await load()
}

onMounted(load)
</script>

<style scoped>
.filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.filter-count {
  margin-left: auto;
  color: #94a3b8;
  font-size: 12px;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}
.detail-head h3 {
  margin: 0;
  font-size: 18px;
  color: #0f172a;
}
.detail-head p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}
.detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  margin: 16px 0;
}
.detail h4 {
  margin: 14px 0 10px;
  font-size: 13px;
  color: #334155;
}
.detail h4 small {
  color: #94a3b8;
  font-weight: 400;
}
@media (max-width: 900px) {
  .detail-grid { grid-template-columns: 1fr; }
}
</style>
