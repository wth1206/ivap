<template>
  <div
    class="dropzone"
    :class="{ active: dragging, disabled }"
    @click="openPicker"
    @dragover.prevent="dragging = true"
    @dragenter.prevent="dragging = true"
    @dragleave.prevent="dragging = false"
    @drop.prevent="onDrop"
  >
    <input ref="inputRef" class="hidden-input" type="file" :accept="accept" @change="onChange" />
    <div class="drop-icon">
      <el-icon :size="28"><UploadFilled /></el-icon>
    </div>
    <div>
      <strong>{{ title }}</strong>
      <p>{{ hint }}</p>
      <p v-if="fileName" class="file-name">{{ fileName }}</p>
    </div>
    <el-button text type="primary" :disabled="disabled">选择文件</el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'

const props = defineProps({
  accept: { type: String, default: '.jpg,.jpeg,.png' },
  title: { type: String, default: '拖拽文件到这里，或点击选择' },
  hint: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  fileName: { type: String, default: '' },
})
const emit = defineEmits(['select'])
const inputRef = ref(null)
const dragging = ref(false)

function openPicker() {
  if (!props.disabled) inputRef.value?.click()
}

function emitFile(file) {
  if (file) emit('select', file)
}

function onChange(event) {
  emitFile(event.target.files?.[0])
  event.target.value = ''
}

function onDrop(event) {
  dragging.value = false
  if (props.disabled) return
  emitFile(event.dataTransfer.files?.[0])
}
</script>

<style scoped>
.dropzone {
  border: 1.5px dashed #cbd5e1;
  border-radius: 14px;
  background: #fbfdff;
  padding: 22px;
  display: flex;
  align-items: center;
  gap: 16px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.dropzone:hover,
.dropzone.active {
  border-color: #2563eb;
  background: #f2f7ff;
}
.dropzone.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.hidden-input {
  display: none;
}
.drop-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #e8f0ff;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: none;
}
strong {
  font-size: 14px;
  color: #1e293b;
}
p {
  margin: 4px 0 0;
  font-size: 12px;
  color: #94a3b8;
}
.file-name {
  color: #2563eb;
  font-weight: 600;
}
</style>
