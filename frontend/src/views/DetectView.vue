<template>
  <div class="page">
    <PageHeader
      title="图像检测"
      description="上传无人机遥感图片，调用 ECE-YOLO 执行真实目标检测。"
    >
      <template #actions>
        <el-button :icon="Clock" @click="$router.push('/history')">历史任务</el-button>
      </template>
    </PageHeader>

    <div class="detect-grid">
      <el-card class="panel" shadow="never" v-loading="loading">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>上传图片</strong>
              <span>JPG / JPEG / PNG，≤20 MB</span>
            </div>
            <el-tag v-if="result?.is_mock" type="warning" effect="light">Mock</el-tag>
          </div>
        </template>

        <UploadDropzone
          accept=".jpg,.jpeg,.png"
          title="拖拽无人机图片到这里"
          hint="建议尺寸 640–2048 px；小目标密集场景建议 conf 0.25 左右"
          :file-name="file?.name || ''"
          :disabled="loading"
          @select="onFile"
        />

        <div v-if="previewUrl" class="preview-box">
          <el-image :src="previewUrl" fit="contain" class="preview-image" :preview-src-list="[previewUrl]" />
          <el-button text type="danger" size="small" @click="clearFile">移除图片</el-button>
        </div>

        <div class="form-row">
          <div class="field">
            <label>检测模型</label>
            <el-select v-model="modelName" placeholder="选择模型" :disabled="loading" style="width: 100%">
              <el-option
                v-for="item in models"
                :key="item.key"
                :label="`${item.display_name}${item.is_mock ? '（Mock）' : ''}`"
                :value="item.key"
                :disabled="!item.available"
              />
            </el-select>
          </div>
          <div class="field">
            <label>置信度阈值 <b>{{ conf.toFixed(2) }}</b></label>
            <el-slider v-model="conf" :min="0.05" :max="0.95" :step="0.05" :disabled="loading" />
          </div>
          <div class="field">
            <label>NMS IoU <b>{{ iou.toFixed(2) }}</b></label>
            <el-slider v-model="iou" :min="0.1" :max="0.9" :step="0.05" :disabled="loading" />
          </div>
        </div>

        <div class="action-row">
          <el-button type="primary" size="large" :icon="Aim" :loading="loading" :disabled="!file" @click="runDetection">
            {{ loading ? '正在推理…' : '开始检测' }}
          </el-button>
          <span class="hint">模型启动后首次请求可能稍慢，之后会复用缓存。</span>
        </div>
      </el-card>

      <el-card v-if="result" class="panel" shadow="never">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>检测结果</strong>
              <span>{{ result.model_name }} · {{ result.inference_time_ms }} ms</span>
            </div>
            <div class="result-actions">
              <el-button size="small" @click="goAnalysis">生成分析报告</el-button>
              <el-button size="small" type="primary" plain @click="goAgent">询问 Agent</el-button>
            </div>
          </div>
        </template>

        <el-alert
          v-if="result.is_mock"
          title="当前为 Mock 检测结果，不代表真实 ECE-YOLO 推理。"
          type="warning"
          :closable="false"
          show-icon
          class="mock-alert"
        />

        <DetectionViewer
          :image-url="result.image_url"
          :result-url="result.result_image"
          :detections="result.detections || []"
        />

        <div class="result-meta">
          <el-descriptions :column="4" border size="small">
            <el-descriptions-item label="任务 ID">{{ result.task_id }}</el-descriptions-item>
            <el-descriptions-item label="目标总数">{{ result.total_objects }}</el-descriptions-item>
            <el-descriptions-item label="图片尺寸">{{ result.width }} × {{ result.height }}</el-descriptions-item>
            <el-descriptions-item label="推理耗时">{{ result.inference_time_ms }} ms</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="result-grid">
          <div>
            <h4>类别统计</h4>
            <ClassBarChart :data="result.class_statistics || {}" :height="240" />
          </div>
          <div>
            <h4>目标明细 <small>{{ result.detections?.length || 0 }} 条</small></h4>
            <el-table :data="result.detections || []" size="small" max-height="240">
              <el-table-column prop="class_name" label="类别" width="100" />
              <el-table-column label="置信度" width="90">
                <template #default="{ row }">{{ (row.confidence * 100).toFixed(1) }}%</template>
              </el-table-column>
              <el-table-column label="bbox" min-width="150">
                <template #default="{ row }">{{ row.bbox.join(', ') }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-card>

      <el-card v-else class="panel result-placeholder" shadow="never">
        <EmptyState
          title="等待检测"
          description="选择图片并点击“开始检测”，结果图、类别统计和目标明细会显示在这里。"
        />
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Aim, Clock } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import UploadDropzone from '@/components/UploadDropzone.vue'
import DetectionViewer from '@/components/DetectionViewer.vue'
import ClassBarChart from '@/components/ClassBarChart.vue'
import EmptyState from '@/components/EmptyState.vue'
import { predictImage } from '@/api/detection'
import { useDetectionStore } from '@/stores/detection'

const router = useRouter()
const detection = useDetectionStore()
const models = computed(() => detection.models)
const modelName = ref('')
const file = ref(null)
const previewUrl = ref('')
const result = ref(null)
const loading = ref(false)
const conf = ref(0.25)
const iou = ref(0.7)

watch(
  () => detection.defaultModel,
  (value) => {
    if (value && !modelName.value) modelName.value = value
  },
)

function onFile(selected) {
  if (!selected) return
  const allowed = ['image/jpeg', 'image/png']
  if (!allowed.includes(selected.type)) {
    ElMessage.warning('仅支持 JPG / PNG 图片')
    return
  }
  if (selected.size > 20 * 1024 * 1024) {
    ElMessage.warning('图片不能超过 20 MB')
    return
  }
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  file.value = selected
  previewUrl.value = URL.createObjectURL(selected)
  result.value = null
}

function clearFile() {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  file.value = null
  previewUrl.value = ''
  result.value = null
}

async function runDetection() {
  if (!file.value) {
    ElMessage.warning('请先选择图片')
    return
  }
  loading.value = true
  try {
    const form = new FormData()
    form.append('file', file.value)
    if (modelName.value) form.append('model_name', modelName.value)
    form.append('conf', String(conf.value))
    form.append('iou', String(iou.value))
    result.value = await predictImage(form)
    ElMessage.success(`检测完成：${result.value.total_objects} 个目标`)
  } finally {
    loading.value = false
  }
}

function goAnalysis() {
  if (result.value?.task_id) {
    router.push({ path: '/analysis', query: { task_id: result.value.task_id } })
  }
}

function goAgent() {
  if (result.value?.task_id) {
    router.push({ path: '/agent', query: { task_id: result.value.task_id } })
  }
}

onMounted(async () => {
  await detection.loadModels()
  if (detection.defaultModel) modelName.value = detection.defaultModel
})

onBeforeUnmount(() => {
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
})
</script>

<style scoped>
.detect-grid {
  display: grid;
  grid-template-columns: minmax(380px, 0.85fr) minmax(0, 1.4fr);
  gap: 16px;
  align-items: start;
}
.preview-box {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.preview-image {
  width: 100%;
  height: 220px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
}
.form-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  margin-top: 16px;
}
.field label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #475569;
  margin-bottom: 6px;
}
.field b {
  color: #2563eb;
}
.action-row {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.hint {
  font-size: 11px;
  color: #94a3b8;
}
.result-actions {
  display: flex;
  gap: 8px;
}
.mock-alert {
  margin-bottom: 12px;
}
.result-meta {
  margin: 12px 0;
}
.result-grid {
  display: grid;
  grid-template-columns: 1fr 1.15fr;
  gap: 18px;
}
.result-grid h4 {
  margin: 4px 0 10px;
  font-size: 13px;
  color: #334155;
}
.result-grid h4 small {
  color: #94a3b8;
  font-weight: 400;
}
.result-placeholder {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}
@media (max-width: 1200px) {
  .detect-grid { grid-template-columns: 1fr; }
  .result-grid { grid-template-columns: 1fr; }
}
</style>
