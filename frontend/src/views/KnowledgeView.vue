<template>
  <div class="page">
    <PageHeader
      title="知识库"
      description="上传 PDF / DOCX / TXT，构建 FAISS 向量索引，检索并给出文档、页码与片段引用。"
    >
      <template #actions>
        <el-tag effect="light">{{ app.vectorStore?.documents || 0 }} 文档 / {{ app.vectorStore?.vectors || 0 }} 向量</el-tag>
      </template>
    </PageHeader>

    <div class="knowledge-grid">
      <el-card class="panel" shadow="never" v-loading="uploading">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>上传文档</strong>
              <span>PDF / DOCX / TXT，≤50 MB</span>
            </div>
          </div>
        </template>
        <UploadDropzone
          accept=".pdf,.docx,.txt"
          title="拖拽知识文档到这里"
          hint="文档会解析、切分、向量化并写入 FAISS；扫描版 PDF 暂不支持 OCR"
          :disabled="uploading"
          :file-name="file?.name || ''"
          @select="onFile"
        />
        <div class="upload-actions">
          <el-button type="primary" :loading="uploading" :disabled="!file" @click="upload">
            {{ uploading ? '解析并索引中…' : '上传并建立索引' }}
          </el-button>
          <el-button v-if="file" text @click="file = null">取消</el-button>
          <span class="hint">{{ app.vectorStore?.embedding_model || 'qwen3.7-text-embedding' }}</span>
        </div>
      </el-card>

      <el-card class="panel" shadow="never">
        <template #header>
          <div class="panel-head">
            <div>
              <strong>文档列表</strong>
              <span>共 {{ store.total }} 份</span>
            </div>
            <el-button text :icon="Refresh" :loading="store.loading" @click="store.loadDocuments()">刷新</el-button>
          </div>
        </template>
        <el-table :data="store.documents" v-loading="store.loading" size="small" max-height="310">
          <el-table-column prop="filename" label="文档" min-width="180" show-overflow-tooltip />
          <el-table-column prop="file_type" label="类型" width="72" />
          <el-table-column prop="page_count" label="页数" width="64" align="center">
            <template #default="{ row }">{{ row.page_count ?? '—' }}</template>
          </el-table-column>
          <el-table-column prop="chunk_count" label="切片" width="64" align="center" />
          <el-table-column label="状态" width="86">
            <template #default="{ row }"><StatusTag :status="row.status" /></template>
          </el-table-column>
          <el-table-column label="操作" width="70">
            <template #default="{ row }">
              <el-button link type="danger" @click="removeDocument(row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <EmptyState title="知识库为空" description="上传第一份专业文档，开始构建 RAG 知识库。" />
          </template>
        </el-table>
      </el-card>
    </div>

    <el-card class="panel search-panel" shadow="never">
      <template #header>
        <div class="panel-head">
          <div>
            <strong>知识检索 / 问答</strong>
            <span>检索 Top-5 片段；问答会保留 [S1] 引用</span>
          </div>
          <el-tag v-if="isMock" type="warning" effect="light">Mock 回答</el-tag>
        </div>
      </template>

      <div class="search-bar">
        <el-input
          v-model="query"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="例如：VisDrone 数据集包含哪些目标类别？"
          @keydown.enter.exact.prevent="ask"
        />
        <div class="search-actions">
          <el-button :loading="searching" :icon="Search" @click="search">检索片段</el-button>
          <el-button type="primary" :loading="asking" :icon="ChatDotRound" @click="ask">知识库问答</el-button>
        </div>
      </div>

      <el-alert
        v-if="noAnswer"
        title="知识库中未检索到与该问题相关的内容，无法基于知识库回答。"
        type="warning"
        :closable="false"
        show-icon
        class="no-answer"
      />

      <div v-if="answer" class="answer-block">
        <h4>回答</h4>
        <MarkdownView :content="answer" />
        <h4>引用来源</h4>
        <CitationList :citations="citations" />
      </div>

      <div v-if="results.length" class="result-block">
        <h4>检索片段 <small>{{ results.length }} 条</small></h4>
        <div class="snippet-list">
          <div v-for="item in results" :key="`${item.document_id}-${item.chunk_index}`" class="snippet">
            <div class="snippet-head">
              <el-tag size="small" effect="light">{{ item.document_name }}</el-tag>
              <span>{{ item.page_no ? `第 ${item.page_no} 页` : '段落/行号见元数据' }}</span>
              <strong>{{ Math.round(item.score * 100) }}%</strong>
            </div>
            <p>{{ item.content }}</p>
          </div>
        </div>
      </div>

      <EmptyState
        v-if="!results.length && !answer && !noAnswer"
        title="输入问题开始检索"
        description="检索只返回片段与来源；问答会调用 LLM 并保留引用。"
      />
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, Refresh, Search } from '@element-plus/icons-vue'
import PageHeader from '@/components/PageHeader.vue'
import UploadDropzone from '@/components/UploadDropzone.vue'
import StatusTag from '@/components/StatusTag.vue'
import MarkdownView from '@/components/MarkdownView.vue'
import CitationList from '@/components/CitationList.vue'
import EmptyState from '@/components/EmptyState.vue'
import {
  askKnowledge,
  deleteDocument,
  searchKnowledge,
  uploadDocument,
} from '@/api/knowledge'
import { useKnowledgeStore } from '@/stores/knowledge'
import { useAppStore } from '@/stores/app'

const store = useKnowledgeStore()
const app = useAppStore()
const file = ref(null)
const uploading = ref(false)
const query = ref('')
const searching = ref(false)
const asking = ref(false)
const results = ref([])
const answer = ref('')
const citations = ref([])
const noAnswer = ref(false)
const isMock = ref(false)

function onFile(selected) {
  if (!selected) return
  const allowed = ['.pdf', '.docx', '.txt']
  const suffix = selected.name.slice(selected.name.lastIndexOf('.')).toLowerCase()
  if (!allowed.includes(suffix)) {
    ElMessage.warning('仅支持 PDF / DOCX / TXT')
    return
  }
  if (selected.size > 50 * 1024 * 1024) {
    ElMessage.warning('文档不能超过 50 MB')
    return
  }
  file.value = selected
}

async function upload() {
  if (!file.value) return
  uploading.value = true
  try {
    const doc = await uploadDocument(file.value)
    ElMessage.success(`已索引：${doc.filename}（${doc.chunk_count} 个切片）`)
    file.value = null
    await store.loadDocuments()
    await app.fetchHealth()
  } finally {
    uploading.value = false
  }
}

async function removeDocument(row) {
  try {
    await ElMessageBox.confirm(`确定删除《${row.filename}》及其向量吗？`, '删除文档', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await deleteDocument(row.document_id)
  ElMessage.success('文档已删除')
  await store.loadDocuments()
  await app.fetchHealth()
}

async function search() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入检索问题')
    return
  }
  searching.value = true
  answer.value = ''
  citations.value = []
  noAnswer.value = false
  isMock.value = false
  try {
    const data = await searchKnowledge({
      query: query.value.trim(),
      top_k: 5,
      score_threshold: 0.25,
    })
    results.value = data.results || []
    noAnswer.value = Boolean(data.no_answer)
  } finally {
    searching.value = false
  }
}

async function ask() {
  if (!query.value.trim()) {
    ElMessage.warning('请输入问题')
    return
  }
  asking.value = true
  results.value = []
  answer.value = ''
  citations.value = []
  noAnswer.value = false
  isMock.value = false
  try {
    const data = await askKnowledge({
      query: query.value.trim(),
      top_k: 5,
      score_threshold: 0.25,
    })
    answer.value = data.answer || ''
    citations.value = data.citations || []
    noAnswer.value = Boolean(data.no_answer)
    isMock.value = Boolean(data.is_mock)
  } finally {
    asking.value = false
  }
}

watch(query, () => {
  if (!query.value.trim()) {
    results.value = []
    answer.value = ''
    citations.value = []
    noAnswer.value = false
  }
})

onMounted(async () => {
  await Promise.allSettled([store.loadDocuments(), app.fetchHealth()])
})
</script>

<style scoped>
.knowledge-grid {
  display: grid;
  grid-template-columns: 0.9fr 1.1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.upload-actions {
  margin-top: 14px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.hint {
  margin-left: auto;
  color: #94a3b8;
  font-size: 11px;
}
.search-panel {
  min-height: 260px;
}
.search-bar {
  display: grid;
  gap: 10px;
}
.search-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}
.no-answer {
  margin-top: 12px;
}
.answer-block,
.result-block {
  margin-top: 18px;
}
.answer-block h4,
.result-block h4 {
  margin: 0 0 10px;
  font-size: 13px;
  color: #334155;
}
.answer-block h4:not(:first-child) {
  margin-top: 18px;
}
.result-block h4 small {
  color: #94a3b8;
  font-weight: 400;
}
.snippet-list {
  display: grid;
  gap: 10px;
}
.snippet {
  border: 1px solid #eef2f7;
  border-radius: 10px;
  padding: 12px 14px;
  background: #fbfdff;
}
.snippet-head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 11px;
  color: #64748b;
}
.snippet-head strong {
  margin-left: auto;
  color: #2563eb;
}
.snippet p {
  margin: 8px 0 0;
  color: #475569;
  font-size: 12.5px;
  line-height: 1.65;
}
@media (max-width: 1200px) {
  .knowledge-grid { grid-template-columns: 1fr; }
}
</style>
