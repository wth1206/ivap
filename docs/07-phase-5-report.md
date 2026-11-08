# 第五阶段实施报告（P5）

> 阶段：P5 RAG 知识库
> 日期：2026-11-06
> 结论：**通过**（PDF/DOCX/TXT 解析、qwen3.7 Embedding、FAISS 检索、真实 LLM 带引用问答；37 个测试通过）
> 设计：[01-architecture-design.md](01-architecture-design.md) §5.5
> 前置：[06-phase-4-report.md](06-phase-4-report.md)

---

## 1. 本阶段目标

1. PDF/DOCX/TXT 解析，保留页码/段落/行号；
2. 清洗、切分、Embedding（1024 维）；
3. FAISS `IndexFlatIP` + 归一化，支持持久化/重建/删除；
4. 上传、列表、删除、检索、带引用问答 API；
5. 检索不到时明确说明“知识库缺少依据”，不调用 LLM 编造；
6. 真实 Embedding + 真实 LLM 验收。

---

## 2. 交付文件

```text
backend/app/rag/
├── cleaner.py          # 空白/控制字符/零宽字符清理
├── loaders.py          # PDF 按页 / DOCX 段落/表格 / TXT 行块
├── splitter.py         # 递归字符切分，保留页码/段落元数据
├── embeddings.py       # OpenAI 兼容 + 确定性 mock
├── vector_store.py     # FAISS 持久化、增删、从 DB 向量重建
└── chain.py            # RAG Prompt + 引用回答

backend/app/services/knowledge_service.py
backend/app/schemas/knowledge.py
backend/app/api/v1/endpoints/knowledge.py
backend/alembic/versions/b0ab7762879b_add_knowledge_chunk_embedding.py
backend/tests/test_knowledge_api.py
```

`knowledge_chunks.embedding` 新增 JSON 列，保存 1024 维向量，使 FAISS 可在不重新调用 Embedding API 的情况下从数据库重建。

---

## 3. 处理流程

```text
上传
 → 扩展名/大小/magic 校验
 → SHA-256 去重
 → 保存 documents/{document_id}/original.ext
 → 解析（PDF 页 / DOCX 段落 / TXT 行块）
 → 清洗
 → 500 字切分，80 字重叠
 → qwen3.7-text-embedding 批量向量化（1024 维）
 → knowledge_documents + knowledge_chunks（含 embedding）
 → FAISS IndexIDMap2(IndexFlatIP) + 归一化
 → 文档状态 ready

检索
 → query 向量化
 → FAISS Top-K*3
 → 阈值过滤
 → 关联 knowledge_chunks/documents
 → 文档名 + 页码/段落 + 片段 + 分数

问答
 → 检索片段 [S1]...
 → 无结果：固定说明，不调用 LLM
 → 有结果：LLM 只基于片段回答，返回引用
```

PDF 使用真实页码（1 起）；DOCX/TXT 没有稳定物理页码，`page_no=null`，在 `extra` 中返回 `paragraph_start/paragraph_end` 或 `line_start/line_end`，不伪造页码。

---

## 4. Embedding 配置

| 项 | 值 |
|---|---|
| Provider | `openai`（阿里云兼容模式） |
| Model | `qwen3.7-text-embedding` |
| Dimension | 1024 |
| Batch | 32 |
| 测试模式 | `EMBEDDING_PROVIDER=mock`，128 维，不联网 |

原配置 `text-embedding-3-small` 在该端点返回 404，已在上一步修正；真实上传/检索已验证。

---

## 5. FAISS 索引

| 项 | 值 |
|---|---|
| 目录 | `backend/vector_db/` |
| 索引 | `IndexIDMap2(IndexFlatIP(1024))` |
| 相似度 | 向量 L2 归一化后的内积 = 余弦 |
| 持久化 | `index.faiss` + `meta.json` |
| 重建 | 从 `knowledge_chunks.embedding` 读取，跳过维度不符的切片 |
| 删除 | 文档级联删除 chunks，重建/移除对应向量 |

`ensure()` 会检查 DB 中 ready 文档的切片数与索引 `ntotal` 是否一致；不一致自动重建，避免索引与数据库漂移。

---

## 6. API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/knowledge/upload` | 上传并索引 PDF/DOCX/TXT |
| GET | `/knowledge/documents` | 分页列表 |
| DELETE | `/knowledge/documents/{document_id}` | 删除文档 + 向量 + 文件 |
| POST | `/knowledge/search` | 相似度检索，返回来源 |
| POST | `/knowledge/ask` | RAG 问答，返回引用（扩展接口） |

`search` / `ask` 参数：

```json
{"query": "...", "top_k": 5, "score_threshold": 0.25, "document_ids": null}
```

引用字段：

```json
{
  "index": 1,
  "document_id": "...",
  "document_name": "visdrone_overview.pdf",
  "page_no": 1,
  "chunk_index": 0,
  "score": 0.8448,
  "snippet": "..."
}
```

---

## 7. 真实验收

上传 3 份文档：

| 文档 | 类型 | 页数 | 切片 |
|---|---|---|---|
| `visdrone.txt` | TXT | null | 1 |
| `ece_yolo.docx` | DOCX | null | 1 |
| `visdrone_overview.pdf` | PDF | 2 | 2 |

健康检查：

```text
vector_store.status = ok
documents = 3
vectors = 4
embedding_model = qwen3.7-text-embedding
```

FAISS meta：

```json
{"dimension": 1024, "embedding_model": "qwen3.7-text-embedding", "count": 4}
```

### 7.1 检索

查询：`VisDrone 数据集包含哪些目标类别？`

| 文档 | 页码 | 分数 |
|---|---|---|
| `visdrone_overview.pdf` | 1 | 0.8448 |
| `visdrone.txt` | null | 0.7317 |
| `ece_yolo.docx` | null | 0.7026 |
| `visdrone_overview.pdf` | 2 | 0.5519 |

`no_answer=false`，PDF 返回真实页码，TXT/DOCX 返回 `page_no=null` 并在 `extra` 中带段落/行号。

### 7.2 真实 RAG 问答

`POST /knowledge/ask` 使用真实 `deepseek-v4-pro`：

```text
no_answer = false
is_mock   = false
citations = 4
answer:
VisDrone2019-DET 数据集包含 10 个目标类别，分别是：
pedestrian（行人）、people（人群）、bicycle（自行车）、car（汽车）、
van（厢式货车）、truck（卡车）、tricycle（三轮车）、
awning-tricycle（带遮阳篷的三轮车）、bus（公共汽车）、motor（摩托车）[S2]。
```

答案引用了 TXT 片段 `[S2]`，引用列表同时返回 PDF/DOCX 片段与页码。

### 7.3 无依据路径

```text
“如何制作巧克力蛋糕？” -> no_answer=true, results=[]
“量子计算的基本原理是什么？” -> no_answer=true, results=[]
```

未调用 LLM 编造答案。

---

## 8. 测试

```text
pytest:    37 passed in 11.62s
ruff:      All checks passed!
```

新增覆盖：

- TXT 上传/列表/检索/问答/重复 409/删除/删除后 no_answer；
- PDF 两页解析，检索结果页码为 1/2；
- DOCX 解析，`page_no=null`，`extra` 有段落元数据；
- 不支持的类型 400；
- 健康检查 vector_store 计数；
- 之前 P1–P4 的 33 个测试全部回归通过。

测试环境使用 `EMBEDDING_PROVIDER=mock` + `LLM_MOCK=true`，不访问真实 API；真实链路单独验收。

---

## 9. 遇到的问题

| 问题 | 原因 | 处理 |
|---|---|---|
| `text-embedding-3-small` 404 | 当前端点没有该模型 | 改用 `qwen3.7-text-embedding`，1024 维，已实测 |
| FAISS 删除/重建需要向量 | 原设计只存索引，删索引后无法重建 | `knowledge_chunks` 增加 `embedding` JSON 列（迁移 `b0ab7762879b`），从 DB 重建 |
| PowerShell 测试中文查询分数偏低/显示乱码 | PS 5.1 对中文请求/响应编码处理不一致 | 用 Python httpx 以 UTF-8 请求复测；真实服务端内容与分数正常 |
| PDF 扫描件无文本 | 没有 OCR | 明确返回 `DOCUMENT_NO_TEXT`，不静默入库空文档 |
| PyMuPDF 在 pytest 有 5 条 DeprecationWarning | SWIG 类型无 `__module__` | 仅告警，不影响解析；未升级依赖 |

---

## 10. 验收清单

- [x] PDF/DOCX/TXT 解析，PDF 保留页码
- [x] DOCX/TXT 不伪造页码，返回段落/行号
- [x] 清洗、500/80 切分
- [x] qwen3.7 Embedding 1024 维
- [x] FAISS 持久化、重建、删除
- [x] 上传/列表/删除/检索/问答 API
- [x] 引用含文档名/页码/片段/分数
- [x] 无结果明确说明，不调 LLM
- [x] 真实检索 + 真实 LLM 问答通过
- [x] 37 个测试通过，ruff 通过
- [x] 健康检查返回文档/向量数

当前数据库保留 3 份知识文档、4 个切片/向量，供 P6/P7 联调。

---

## 11. 下一阶段（P6）

P6 将用 LangGraph 构建 Agent，注册 5 个工具：

1. `detect_image`：调用 YOLO 检测；
2. `get_detection_result`：查询检测结果；
3. `get_detection_statistics`：统计历史任务；
4. `search_knowledge_base`：调用 RAG 检索；
5. `generate_analysis_report`：生成分析报告。

P6 不需要新增 Key；知识库与检测任务已有真实数据可做工具联调。
