<template>
  <div v-if="citations.length" class="citation-list">
    <div v-for="item in citations" :key="`${item.document_id}-${item.page_no}-${item.chunk_index}`" class="citation-card">
      <div class="citation-head">
        <el-tag size="small" effect="dark" type="primary">[S{{ item.index }}]</el-tag>
        <strong>{{ item.document_name }}</strong>
        <span class="citation-page">
          {{ item.page_no ? `第 ${item.page_no} 页` : '段落/行号见片段' }}
        </span>
        <span class="citation-score">{{ Math.round((item.score || 0) * 100) }}%</span>
      </div>
      <p>{{ item.snippet }}</p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  citations: { type: Array, default: () => [] },
})
</script>

<style scoped>
.citation-list {
  display: grid;
  gap: 10px;
}
.citation-card {
  border: 1px solid #e8eef7;
  background: #fbfdff;
  border-radius: 10px;
  padding: 12px 14px;
}
.citation-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.citation-head strong {
  font-size: 13px;
  color: #1e293b;
}
.citation-page {
  font-size: 12px;
  color: #64748b;
}
.citation-score {
  margin-left: auto;
  font-size: 12px;
  color: #2563eb;
  font-weight: 600;
}
p {
  margin: 8px 0 0;
  color: #64748b;
  font-size: 12.5px;
  line-height: 1.65;
}
</style>
