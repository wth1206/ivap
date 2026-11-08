<template>
  <div v-if="calls.length" class="tool-list">
    <div v-for="(call, index) in calls" :key="`${call.name}-${index}`" class="tool-row">
      <el-icon :class="call.status === 'success' ? 'ok' : 'err'">
        <CircleCheck v-if="call.status === 'success'" />
        <CircleClose v-else />
      </el-icon>
      <span class="tool-name">{{ call.name }}</span>
      <el-tag size="small" :type="call.status === 'success' ? 'success' : 'danger'" effect="light">
        {{ call.status === 'success' ? '成功' : '失败' }}
      </el-tag>
      <span class="tool-duration">{{ call.duration_ms }} ms</span>
      <code class="tool-args">{{ argumentsText(call.arguments) }}</code>
    </div>
  </div>
</template>

<script setup>
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'

defineProps({
  calls: { type: Array, default: () => [] },
})

function argumentsText(args) {
  if (!args) return ''
  const text = JSON.stringify(args)
  return text.length > 90 ? `${text.slice(0, 90)}…` : text
}
</script>

<style scoped>
.tool-list {
  display: grid;
  gap: 6px;
  margin: 10px 0;
}
.tool-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  background: #f8fafc;
  border: 1px solid #eef2f7;
  border-radius: 8px;
  padding: 7px 10px;
  font-size: 12px;
}
.ok { color: #16a34a; }
.err { color: #dc2626; }
.tool-name {
  font-weight: 600;
  color: #334155;
}
.tool-duration {
  color: #94a3b8;
}
.tool-args {
  color: #64748b;
  font-size: 11px;
  margin-left: auto;
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
