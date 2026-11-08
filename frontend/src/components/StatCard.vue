<template>
  <div class="stat-card" :class="`tone-${tone}`">
    <div class="stat-copy">
      <span class="stat-label">{{ label }}</span>
      <strong class="stat-value">{{ value }}</strong>
      <span v-if="hint" class="stat-hint">{{ hint }}</span>
    </div>
    <div class="stat-icon">
      <el-icon :size="22"><component :is="icon" /></el-icon>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '0' },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'blue' },
  icon: { type: [Object, String], default: 'DataLine' },
})
</script>

<style scoped>
.stat-card {
  display: flex;
  justify-content: space-between;
  padding: 20px 22px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #e9eef6;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}
.stat-copy {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-label {
  color: #64748b;
  font-size: 13px;
}
.stat-value {
  font-size: 28px;
  line-height: 1.1;
  color: #0f172a;
  font-weight: 700;
}
.stat-hint {
  color: #94a3b8;
  font-size: 12px;
}
.stat-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.tone-blue .stat-icon { background: #e8f0ff; color: #2563eb; }
.tone-green .stat-icon { background: #e8f8f0; color: #16a34a; }
.tone-amber .stat-icon { background: #fff6e5; color: #d97706; }
.tone-violet .stat-icon { background: #f2ecff; color: #7c3aed; }
</style>
