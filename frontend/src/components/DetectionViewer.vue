<template>
  <div class="viewer">
    <div class="viewer-head">
      <div class="viewer-label">
        <el-tag size="small" effect="light" :type="showResult && resultUrl ? 'success' : 'info'">
          {{ showResult && resultUrl ? '检测结果图' : '原始图片' }}
        </el-tag>
        <span v-if="detections.length" class="viewer-count">{{ detections.length }} 个目标</span>
      </div>
      <el-switch
        v-if="resultUrl"
        v-model="showResult"
        inline-prompt
        active-text="结果"
        inactive-text="原图"
      />
    </div>
    <el-image
      class="viewer-image"
      :src="displayUrl"
      :preview-src-list="previewList"
      fit="contain"
      hide-on-click-modal
    >
      <template #error>
        <div class="image-error">图片加载失败</div>
      </template>
    </el-image>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  imageUrl: { type: String, default: '' },
  resultUrl: { type: String, default: '' },
  detections: { type: Array, default: () => [] },
})

const showResult = ref(true)
watch(
  () => props.resultUrl,
  (value) => {
    showResult.value = Boolean(value)
  },
)

const displayUrl = computed(() =>
  showResult.value && props.resultUrl ? props.resultUrl : props.imageUrl,
)
const previewList = computed(() => [displayUrl.value].filter(Boolean))
</script>

<style scoped>
.viewer {
  border: 1px solid #e8eef7;
  border-radius: 12px;
  overflow: hidden;
  background: #0f172a;
}
.viewer-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid #eef2f7;
}
.viewer-label {
  display: flex;
  align-items: center;
  gap: 8px;
}
.viewer-count {
  font-size: 12px;
  color: #64748b;
}
.viewer-image {
  width: 100%;
  height: 420px;
  display: block;
  background: #0f172a;
}
.image-error {
  height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}
</style>
