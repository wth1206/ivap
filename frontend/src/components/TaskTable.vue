<template>
  <el-table :data="tasks" v-loading="loading" row-key="task_id" stripe>
    <el-table-column label="图片" width="86">
      <template #default="{ row }">
        <el-image
          v-if="row.image_url"
          :src="row.image_url"
          fit="cover"
          class="thumb"
          :preview-src-list="[row.image_url]"
          preview-teleported
        >
          <template #error><div class="thumb-fallback">IMG</div></template>
        </el-image>
        <div v-else class="thumb-fallback">IMG</div>
      </template>
    </el-table-column>
    <el-table-column prop="image_name" label="图片名称" min-width="180" show-overflow-tooltip />
    <el-table-column prop="model_name" label="模型" width="110" />
    <el-table-column label="状态" width="92">
      <template #default="{ row }"><StatusTag :status="row.status" /></template>
    </el-table-column>
    <el-table-column prop="total_objects" label="目标数" width="80" align="center" />
    <el-table-column label="推理耗时" width="100" align="right">
      <template #default="{ row }">
        {{ row.inference_time_ms ? `${row.inference_time_ms} ms` : '-' }}
      </template>
    </el-table-column>
    <el-table-column label="创建时间" width="170">
      <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
    </el-table-column>
    <el-table-column v-if="showActions" label="操作" width="210" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="$emit('view', row)">详情</el-button>
        <el-button link type="primary" @click="$emit('analyze', row)">分析</el-button>
        <el-button link type="danger" @click="$emit('delete', row)">删除</el-button>
      </template>
    </el-table-column>
    <template #empty>
      <EmptyState title="暂无检测任务" description="上传一张无人机图片开始第一次检测。" />
    </template>
  </el-table>
</template>

<script setup>
import StatusTag from './StatusTag.vue'
import EmptyState from './EmptyState.vue'
import { formatDate } from '@/utils/format'

defineProps({
  tasks: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  showActions: { type: Boolean, default: true },
})
defineEmits(['view', 'analyze', 'delete'])
</script>

<style scoped>
.thumb {
  width: 56px;
  height: 40px;
  border-radius: 6px;
  display: block;
}
.thumb-fallback {
  width: 56px;
  height: 40px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
