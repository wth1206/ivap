<template>
  <div class="empty-state">
    <el-icon :size="34"><Box /></el-icon>
    <strong>{{ title }}</strong>
    <p>{{ description }}</p>
    <slot name="action" />
  </div>
</template>

<script setup>
import { Box } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '完成一次操作后，这里会展示结果。' },
})
</script>

<style scoped>
.empty-state {
  padding: 40px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #94a3b8;
  text-align: center;
}
strong {
  color: #475569;
  font-size: 15px;
}
p {
  margin: 0;
  font-size: 13px;
}
</style>
