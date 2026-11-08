# IVAP 项目开发全流程记录

> 文档性质：开发全过程归档，不替代各阶段实施报告。
> 项目：智能视觉分析平台（Intelligent Vision Analysis Platform，IVAP）
> 时间：2026-11-06 ～ 2026-11-07
> 状态：P1–P8 全部完成
> 入口：[README](../README.md) · [归档说明](13-handover-and-archive.md)

---

## 1. 项目定义

### 1.1 目标

面向无人机遥感图像，提供一条可运行、可解释、可追溯的完整链路：

```text
图片上传
  → ECE-YOLO 真实检测
  → Python 统计事实
  → LLM 生成 8 段分析报告
  → RAG 知识库专业问答（带引用）
  → LangGraph Agent 自然语言调用工具
  → Vue 3 前端 + MySQL 持久化 + Docker 部署
```

### 1.2 三条硬约束

1. **统计事实由 Python 计算**：数量、类别、密度、边缘比例、最近邻距离、IoU 等全部在 `stats.py` 中计算。
2. **LLM 不得编造检测数量、模型性能、实验数据**：Prompt 只允许解释 facts；缺少依据必须说明。
3. **Mock 必须显式标记**：`is_mock=true` 贯穿 API 与前端；Mock 结果不能冒充真实 ECE-YOLO / LLM 结果。

### 1.3 非目标

- 不做模型训练平台；
- 不做多租户权限系统（`AUTH_ENABLED` 预留）；
- 不做视频流实时检测；
- 不承诺 mAP 复现实验（只使用 checkpoint 自带训练记录，并明确标注）。

---

## 2. 开发阶段总览

| 阶段 | 日期 | 目标 | 关键结果 |
|---|---|---|---|
| P1 | 11-06 | 工程骨架、配置、日志、异常、健康检查、pytest | FastAPI 可启动，37→45 测试基线建立 |
| P2 | 11-06 | MySQL 8.0、SQLAlchemy、Alembic、任务 CRUD、上传 | 8 张表；MySQL 127.0.0.1:3306 |
| P3 | 11-06 | ECE-YOLO 接入、mmcv 兼容、推理、绘图 | 10 类；GPU 33 目标；CPU 可运行 |
| P4 | 11-06 | LLM 分析报告、facts-only Prompt、落库 | 8 段报告；真实报告 34.9s |
| P5 | 11-06 | PDF/DOCX/TXT、切分、Embedding、FAISS、引用 | 3 文档 / 4 向量；真实 RAG 回答 |
| P6 | 11-06 | LangGraph、5 工具、会话、工具轨迹 | `deepseek-v4-pro` 工具调用通过 |
| P7 | 11-07 | Vue 3 六页面、Element Plus、ECharts、Markdown | 生产构建；浏览器冒烟 0 错误 |
| P8 | 11-07 | Docker Desktop + WSL2、三容器、Nginx、部署 | 3/3 healthy；检测/RAG/Agent/报告/持久化通过 |

各阶段详细报告：

```text
docs/02-phase-1-report.md
docs/03-ece-yolo-integration-notes.md
docs/04-phase-2-report.md
docs/05-phase-3-report.md
docs/06-phase-4-report.md
docs/07-phase-5-report.md
docs/08-phase-6-report.md
docs/09-phase-7-report.md
docs/10-deployment.md
docs/11-phase-8-report.md
```

---

## 3. 总体架构

```text
┌───────────────────────────────────────────────────────────────┐
│ Vue 3 前端（8080 / 5173）                                      │
│ 首页 · 检测 · 分析 · 知识库 · Agent · 历史                    │
└──────────────────────────────┬────────────────────────────────┘
                               │ /api/v1, /static
┌──────────────────────────────▼────────────────────────────────┐
│ Nginx（Docker）或 Vite Proxy（开发）                           │
└──────────────────────────────┬────────────────────────────────┘
                               │
┌──────────────────────────────▼────────────────────────────────┐
│ FastAPI（8000，单 worker）                                     │
│                                                               │
│  API 层：health / detection / analysis / knowledge / chat      │
│  Service 层：detection / stats / analysis / knowledge / chat   │
│  Algorithm：ModelManager → ECE-YOLO / Mock                    │
│  RAG：parse → clean → split → embed → FAISS → search/ask      │
│  Agent：LangGraph StateGraph + 5 tools                         │
│  LLM：OpenAI 兼容 chat / tools / JSON mode                     │
└───────┬───────────────────┬───────────────────┬───────────────┘
        │                   │                   │
   MySQL 8.0           FAISS 索引           LLM / Embedding
   （业务数据）         （知识向量）          （外部 HTTPS）
```

### 3.1 前端

- Vue 3.5 + Vite 6 + Element Plus 2.9 + Pinia + Vue Router；
- ECharts 5.6 类别柱状图；
- markdown-it + DOMPurify 渲染 LLM 报告 / Agent 回答；
- 6 个页面，Nginx 生产托管。

### 3.2 后端

- Python 3.9.21、FastAPI 0.115、Pydantic 2、SQLAlchemy 2、Alembic；
- 单进程加载 ECE-YOLO 与 FAISS，**必须单 worker**；
- 统一配置 `app/core/config.py`，`.env` 注入；
- 统一错误体 `{error: {code, message, details, request_id}}`。

### 3.3 视觉

- PyTorch 2.1.2、torchvision 0.16.2、Ultralytics 8.3.209、OpenCV 4.11；
- ECE-YOLO 自定义模块：`ESPMStem`、`RepNCSPELAN4`、`DynamicHead`；
- 本机无 mmcv，使用 `torchvision.ops.deform_conv2d` 的进程内 shim；
- `models.yaml` 注册 `ece-yolo` 与 `mock` 两个适配器。

### 3.4 数据与知识

- MySQL 8.0.28，utf8mb4；
- 开发测试使用 SQLite 临时库，不污染 MySQL；
- FAISS `IndexIDMap2(IndexFlatIP)` + L2 归一化，余弦相似度；
- Embedding：`qwen3.7-text-embedding`，维度 1024。

---

## 4. 代码结构

```text
ivap/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app factory / lifespan / CORS / static
│   │   ├── core/                   # config/logging/exceptions/middleware/security
│   │   ├── db/                     # engine/session/base/types/init_db
│   │   ├── models/                 # 8 张表
│   │   ├── schemas/                # Pydantic 契约
│   │   ├── api/v1/                 # health/detection/analysis/knowledge/chat
│   │   ├── services/               # storage/detection/stats/llm/analysis/knowledge/chat
│   │   ├── algorithms/             # registry/model_manager/mock/visualize/ECE-YOLO
│   │   ├── rag/                    # cleaner/loaders/splitter/embeddings/vector_store
│   │   └── agents/                 # state/prompts/tools/graph/runner
│   ├── alembic/                    # 2 个 migration，head=b0ab7762879b
│   ├── config/models.yaml
│   ├── tests/
│   └── Dockerfile
├── frontend/
│   ├── src/api/                    # axios 封装
│   ├── src/components/             # 布局/图表/上传/查看器/Markdown/引用/工具轨迹
│   ├── src/views/                  # 6 页面
│   ├── src/stores/                 # app/detection/knowledge/chat
│   ├── nginx.conf
│   └── Dockerfile
├── docs/                           # 架构 + P1–P8 报告 + 部署
├── samples/                        # 示例图片与知识文档
├── scripts/                        # MySQL/后端/前端/Docker 启停
├── docker-compose.yml
├── docker-compose.gpu.yml
├── .env.example
├── .env.docker.example
└── best.pt                         # 用户提供，gitignore
```

---

## 5. 数据模型

| 表 | 作用 | 关键字段 |
|---|---|---|
| `users` | 用户预留 | username / password_hash / is_active |
| `detection_tasks` | 检测任务 | id / image_path / model_name / status / total_objects / conf / iou |
| `detection_results` | 单个目标 | task_id / class_id / class_name / confidence / bbox |
| `llm_reports` | 分析报告 | task_id / content / structured / model_name / is_mock / latency_ms / usage |
| `knowledge_documents` | 知识文档 | filename / file_type / status / page_count / chunk_count |
| `knowledge_chunks` | 文档切片 | document_id / chunk_index / content / page_no / embedding(JSON) |
| `conversations` | Agent 会话 | id / title / updated_at |
| `chat_messages` | 会话消息 | conversation_id / role / content / tool_calls / citations / token_usage |

关系：

```text
detection_tasks 1 ─── n detection_results
detection_tasks 1 ─── n llm_reports
knowledge_documents 1 ─── n knowledge_chunks
conversations 1 ─── n chat_messages
```

---

## 6. API 契约

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 数据库 / 模型 / LLM / 向量库 |
| GET | `/health` | 容器探针别名 |
| POST | `/api/v1/detection/predict` | 上传并真实推理 |
| POST | `/api/v1/detection/upload` | 只上传，创建 pending 任务 |
| GET | `/api/v1/detection/tasks` | 分页 / 关键词 / 状态 / 模型 / 时间 |
| GET | `/api/v1/detection/tasks/{task_id}` | 任务详情 + 目标框 |
| DELETE | `/api/v1/detection/tasks/{task_id}` | 删除任务与图片 |
| GET | `/api/v1/detection/models` | 模型列表与可用性 |
| GET | `/api/v1/detection/overview` | 首页统计 + 类别分布 |
| POST | `/api/v1/analysis/{task_id}` | 生成 / 复用 8 段报告 |
| GET | `/api/v1/analysis/{task_id}` | 最新报告 |
| POST | `/api/v1/knowledge/upload` | 上传并索引 |
| GET | `/api/v1/knowledge/documents` | 文档列表 |
| DELETE | `/api/v1/knowledge/documents/{id}` | 删除文档与向量 |
| POST | `/api/v1/knowledge/search` | Top-K 片段检索 |
| POST | `/api/v1/knowledge/ask` | RAG 回答 + 引用 |
| POST | `/api/v1/chat` | Agent 对话 |
| GET | `/api/v1/chat/history` | 会话列表 / 消息 |

统一错误体：

```json
{
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "检测任务不存在",
    "details": {},
    "request_id": "..."
  }
}
```

---

## 7. 五条核心链路

### 7.1 检测链路

```text
UploadFile
→ 扩展名 / MIME / magic bytes / 大小校验
→ 生成 task_id，保存原图
→ ModelManager 获取 ECE-YOLO（单例 + 锁）
→ Ultralytics 推理
→ DetectionResult 批量写入
→ stats.py 计算密度/分布/边缘/尺寸/置信度/IoU
→ visualize.py 绘制结果图
→ 更新 task 状态 / 耗时
→ 返回 task_id / 统计 / URL / 明细
```

关键：检测参数 `imgsz=640, conf=0.25, iou=0.7, max_det=300`；首次推理前做 dummy warmup。

### 7.2 分析链路

```text
检测任务
→ Python 生成 facts（8 段所需统计）
→ 固定 8 段 JSON Prompt
→ LLM JSON mode
→ extract_json + Pydantic 校验
→ 缺失/非法字段拒绝
→ 写入 llm_reports
```

8 段：基本信息、总体数量、类别分布、密集程度、空间分布、检测特点、风险/限制、总结建议。

防幻觉：

- facts 明确低/高置信度阈值（0.4 / 0.7）；
- 密度阈值（稀疏 <5、中等 5–20、密集 20–50、极密集 >50 / 百万像素）；
- Prompt 禁止改写统计数字；
- `is_mock` 标记。

### 7.3 RAG 链路

```text
PDF/DOCX/TXT
→ PyMuPDF / python-docx / text loader
→ 清洗（空白、页眉页脚、乱码）
→ LangChain RecursiveCharacterTextSplitter
→ qwen3.7-text-embedding（1024）
→ L2 normalize
→ FAISS IndexIDMap2(IndexFlatIP)
→ 持久化 index.faiss + meta.json
→ Top-K 检索
→ score_threshold 过滤
→ LLM 基于片段回答
→ [S1]/[S2] 引用
```

无相关片段时返回 `no_answer=true`，不强行回答。

### 7.4 Agent 链路

```text
START
 → prepare（系统提示 + 当前 task_id/image_path + 历史）
 → agent（LLM + tools schema）
 → 有 tool_calls 且 step < 6 → tools
 → 回到 agent
 → 无 tool_calls → finalize → END
```

5 个工具：

1. `detect_image`
2. `get_detection_result`
3. `get_detection_statistics`
4. `search_knowledge_base`
5. `generate_analysis_report`

规则：Pydantic 参数校验、失败作为工具消息返回、单工具输出截断 12k、最大 6 轮、超时 180s。

### 7.5 前端链路

```text
Vue Router
├── /            首页：统计/图表/健康/最近任务
├── /detect      上传/参数/结果图/类别图/目标表
├── /analysis    任务选择/8 段 Markdown/复制
├── /knowledge   上传/列表/删除/检索/问答/引用
├── /agent       会话/任务绑定/工具轨迹/引用
└── /history     筛选/分页/详情抽屉/删除
```

Axios 统一错误码与 message；Markdown 经 DOMPurify；图片走 `/static`。

---

## 8. 各阶段关键实现与验收

### P1 工程骨架

- FastAPI app factory、lifespan、CORS、静态目录、统一异常/中间件/request_id；
- 配置 `pydantic-settings`，路径相对项目根解析；
- 健康检查；
- 测试基线。

### P2 MySQL 与任务

- 本机便携 MySQL 8.0.28，utf8mb4；
- 8 张表 + Alembic；
- 上传安全检查；任务列表/详情/删除；Mock 检测；
- 测试隔离 SQLite。

### P3 ECE-YOLO

- 复制 3 个自定义模块到 `vendor/`，不依赖外部仓库；
- `mmcv_shim.py` 适配 `ModulatedDeformConv2d`；
- 权重 `best.pt`，10 类；
- checkpoint 训练记录（不是本项目复现）：mAP50=0.37453、mAP50-95=0.22325；
- GPU 验证 33 目标；warmup 后 296ms → 47ms（RTX 2060）；CPU 约 507ms。

### P4 LLM 报告

- `LLMService.chat_text/chat_json`；
- 8 段 Prompt + JSON 校验；
- 真实报告 34.9s，2604 prompt + 1928 completion；
- 首次报告 LLM 改写阈值，加入显式阈值 facts 后修复并重生成。

### P5 RAG

- PDF/DOCX/TXT 解析、清洗、切分；
- `qwen3.7-text-embedding`，1024 维；
- FAISS 持久化 + 重载；
- 3 文档 / 4 向量；真实问答引用 `[S2]`；
- 无答案路径验证。

### P6 Agent

- LangGraph 5 节点；
- 5 工具真实调用；
- 会话 / 消息 / tool_calls / citations 落库；
- 真实 `deepseek-v4-pro` function calling 通过；
- 检测 → 新任务写入上下文。

### P7 前端

- Vue 3 六页面；
- 结果图、类别图、Markdown 报告、引用、工具轨迹；
- 生产构建 2143 modules，主包 89KB（manualChunks）；
- Chrome headless 冒烟：检测、知识检索、Agent 历史、Agent 发送；0 控制台错误。

### P8 Docker

- Docker Desktop 4.98 + WSL 3.0.1；
- backend/frontend/MySQL 三容器；
- Nginx SPA + `/api` + `/static`；
- 真实检测 32 目标 / 473ms（CPU）；
- RAG、Agent、报告 42.96s；
- 数据卷 down/up 持久化；
- 45 测试 + ruff + alembic + compose config。

---

## 9. 关键技术决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 数据库 | MySQL 8.0 | 业务需要持久化、并发与迁移；SQLite 仅测试 |
| P2 方案 | 先装 MySQL 再开发 | 避免后期迁移 |
| P3 模块 | 复制 3 个模块进项目 | 可复现，不依赖外部路径 |
| 模型 | ECE-YOLO（非 DED-YOLO） | 用户指定权重 |
| 统计 | Python 计算 | 防 LLM 编造 |
| Mock | 显式 `is_mock` | 不冒充真实结果 |
| Embedding | qwen3.7-text-embedding / 1024 | 与真实 API 匹配 |
| Agent | LangGraph + 5 tools | 可观测、可限制步数 |
| 部署 | 单 worker | 模型/FAISS 在进程内 |
| Docker | CPU 默认 + GPU overlay | 无 GPU 环境也能运行 |

---

## 10. 测试与验证矩阵

| 层级 | 内容 | 结果 |
|---|---|---|
| 后端单元/接口 | 45 个 pytest | ✅ |
| 静态检查 | ruff | ✅ |
| 依赖 | pip check | ✅ |
| 迁移 | alembic check | ✅ |
| 前端构建 | vite build | ✅ |
| 浏览器冒烟 | Chrome + puppeteer | ✅ |
| Docker 配置 | compose config | ✅ |
| 容器健康 | 3/3 healthy | ✅ |
| 真实检测 | 33（GPU）/32（CPU） | ✅ |
| 真实 RAG | 4 引用 / 0.7317 | ✅ |
| 真实 Agent | 工具调用成功 | ✅ |
| 真实报告 | 42.96s / 1934 字符 | ✅ |
| 持久化 | down/up | ✅ |

---

## 11. 复现方式

### 11.1 本地开发

```powershell
# MySQL
scripts\mysql_start.cmd

# 后端（新窗口）
scripts\run_backend.cmd

# 前端（新窗口）
scripts\run_frontend.cmd
```

- 后端：<http://127.0.0.1:8000/docs>
- 前端：<http://127.0.0.1:5173>

### 11.2 Docker

```powershell
Copy-Item .env.docker.example .env.docker
# 填写 MySQL / LLM / Embedding 密钥
docker compose --env-file .env.docker up -d --build
```

- 前端：<http://localhost:8080>
- Swagger：<http://localhost:8000/docs>

### 11.3 示例数据

```text
samples/visdrone-sample.jpg
samples/knowledge/visdrone.txt
samples/knowledge/ece_yolo.docx
samples/knowledge/visdrone_overview.pdf
```

---

## 12. 已知限制与风险

1. 单 worker；水平扩展需拆分模型服务和向量服务。
2. 未做用户鉴权（`AUTH_ENABLED` 预留）。
3. GPU overlay 未在 Docker Desktop WSL GPU 环境验收。
4. 扫描版 PDF 未做 OCR。
5. Docker Hub / PyTorch 国内网络需要镜像；部署指南有处理。
6. 示例数据与真实业务数据隔离；不要混用。
7. 模型 checkpoint 训练指标来自权重自带记录，不是本项目复现。

---

## 13. 归档说明

源码、文档、示例与 `best.pt` 的归档包、校验和、包含/排除清单见：

- [归档与交接说明](13-handover-and-archive.md)
- `archive/IVAP-source-20261108.zip`
- `archive/IVAP-source-20261108.sha256.txt`

归档包不包含：`.env`、`.env.docker`、`.venv`、`.mysql`、`node_modules`、`dist`、上传图片、运行时日志、FAISS 运行时索引、MySQL 数据。
