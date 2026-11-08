# 简历项目写法（IVAP）

> 定位：**个人项目 / 全栈 + 算法工程**。不要写成公司业务项目。
> 原则：只写真实跑过的东西；模型指标不要冒充自己训练的结果。

---

## 1. 简历项目条目（推荐中文版）

### 智能视觉分析平台（IVAP）｜个人项目｜2026.11

**技术栈**：Python、FastAPI、MySQL、SQLAlchemy、PyTorch、ECE-YOLO、Vue 3、Element Plus、ECharts、FAISS、LangGraph、Docker Compose、Nginx

**项目描述**：面向无人机遥感图像的端到端智能分析平台，覆盖图片检测、统计事实、LLM 分析报告、RAG 知识库问答、LangGraph Agent 与前端可视化。

**核心工作**：

- 设计并实现 **Vue 3 + FastAPI + MySQL** 的 6 页面平台与 17 个 API，落地检测任务、分析报告、知识库、Agent 会话等 **8 张表**；用 Docker Compose 编排 MySQL、后端、Nginx 前端三容器。
- 接入 **ECE-YOLO** 自定义结构（ESPMStem、RepNCSPELAN4、DynamicHead），在缺少 mmcv 的环境下用 `torchvision.ops.deform_conv2d` 实现进程内兼容层，完成 10 类目标检测、结果图绘制与任务持久化；RTX 2060 预热后单图推理约 **47 ms**，CPU 路径约 **0.5 s**。
- 设计“**Python 算统计、LLM 只解释**”的报告链路：8 个固定章节、JSON Schema 校验、低/高置信度与密度阈值显式注入 Prompt，避免 LLM 改写检测数量；真实报告生成约 **35–43 s**。
- 构建 RAG 知识库：支持 PDF/DOCX/TXT 解析、清洗、切分，使用 **qwen3.7 1024 维 Embedding + FAISS** 检索，回答保留 `[S1]` 文档/页码引用；无相关片段时返回 `no_answer`，不强行编造。
- 实现 **LangGraph Agent**：5 个工具（检测、任务详情、统计、知识检索、报告生成）、最多 6 轮、180 s 超时；工具参数 Pydantic 校验，失败作为工具消息回传；会话、工具轨迹、引用与 token 用量落库。
- 完成工程化交付：**45 个 pytest**、ruff、Alembic 迁移、前端生产构建、Chrome 无头浏览器冒烟、Docker 三容器 **3/3 healthy**、数据卷 down/up 持久化验证。

**项目结果**：在 VisDrone 示例图上完成真实检测与 8 段分析报告；知识库问答返回带引用答案；Docker 环境一条命令启动全栈。

---

## 2. 更短版本（一页简历，3–4 条）

- 独立完成无人机遥感图像智能分析平台：Vue 3 + FastAPI + MySQL + ECE-YOLO + RAG + LangGraph Agent，Docker Compose 三容器部署。
- 接入 ECE-YOLO 自定义模块并实现 mmcv-free 兼容层；10 类检测，RTX 2060 预热后单图约 47 ms，完成结果图、统计与任务持久化。
- 设计 facts-only LLM 报告链路（8 段、JSON 校验、阈值注入），避免编造检测数量；FAISS + qwen 1024 维 Embedding 实现带 `[S1]` 引用的 RAG 问答。
- 实现 5 工具 LangGraph Agent（最多 6 轮/180 s）与 6 页面前端；45 个测试、ruff、前端构建、Docker 3/3 healthy。

---

## 3. STAR 面试讲述稿

### Situation

无人机遥感图像目标小、分布密、人工分析效率低；现有 Demo 往往只做检测框展示，缺少统计解释、知识依据和可追溯的工具调用。

### Task

做一个可运行的端到端平台：真实检测、可解释报告、知识库问答、Agent 编排，并且统计数字不能被 LLM 编造。

### Action

1. 用 FastAPI 分层架构落地检测/分析/知识库/Agent API，MySQL 8 张表持久化；
2. 接入 ECE-YOLO 的三个自定义模块，写 mmcv 兼容层，解决权重加载与 deform conv 输出尺寸问题；
3. 把数量/密度/空间分布/置信度/IoU 全部放到 Python `stats.py`，LLM 只拿 facts 生成 8 段 JSON 报告；
4. 用 qwen Embedding + FAISS 建 RAG，切片保留文档/页码，回答必须引用；
5. 用 LangGraph 把 5 个工具串成状态机，限制 6 轮/180 s，工具错误原样回传；
6. 用 Vue 3 做 6 页面，Docker Compose + Nginx 部署，补测试与浏览器冒烟。

### Result

- 真实检测：VisDrone 示例图 33 个目标（GPU）/ 32 个（CPU Docker）；
- 真实报告：8 段，约 35–43 s；
- RAG：3 文档 / 4 向量，回答带 `[S1]` 引用；
- Agent：真实 `deepseek-v4-pro` 工具调用通过；
- 工程：45 个测试、ruff、3 容器 healthy、数据卷持久化。

---

## 4. 面试可能追问

| 问题 | 回答要点 |
|---|---|
| 为什么统计不交给 LLM？ | LLM 会改写数字/阈值；统计必须可复现、可校验，Python 算完再给 LLM 解释 |
| mmcv 缺失怎么办？ | 用 torchvision `deform_conv2d`，按 mmcv 输出尺寸裁剪 offset；CPU/GPU 都验证 |
| 怎么防 RAG 胡编？ | 相似度阈值 + `no_answer` + 强制引用 + 前端展示来源 |
| Agent 工具失败怎么办？ | 不抛 500，转成 `{error:{code,message}}` 工具消息；限制轮数/超时；轨迹落库 |
| 为什么单 worker？ | 模型/FAISS 在进程内；多 worker 会重复加载且状态不一致 |
| Docker 里遇到什么问题？ | Docker Hub 超时→mirror；PyTorch 源慢→阿里云 wheel；ultralytics 升 NumPy 2→pin 1.26.4 |
| 模型 mAP 多少？ | checkpoint 自带训练记录 mAP50=0.37453，但**不是我训练/复现**；简历不把它当个人成果 |

---

## 5. 不要这样写

- ❌ “训练了 ECE-YOLO，mAP 达到 0.37” —— 权重是现成的，训练指标来自 checkpoint 记录。
- ❌ “支持高并发/百万级数据” —— 没有做过压测，且当前单 worker。
- ❌ “检测 33 个目标” 不加限定 —— 这是特定 VisDrone 示例图；CPU Docker 为 32。
- ❌ “47 ms 端到端” —— 47 ms 是 RTX 2060 预热后的模型推理，不含上传/绘图/落库。
- ❌ 把 Mock 结果写成真实结果 —— 项目里 `is_mock` 标记必须保留。

---

## 6. 可选英文版

**Intelligent Vision Analysis Platform (IVAP) — Personal Project**

Built an end-to-end UAV remote-sensing analysis platform with Vue 3, FastAPI, MySQL, ECE-YOLO, FAISS-based RAG, LangGraph Agent, and Docker Compose.

- Integrated ECE-YOLO custom modules with a mmcv-free deform-conv shim; 10-class detection, ~47 ms warmed GPU inference on RTX 2060.
- Designed a facts-only LLM reporting pipeline (8 sections, JSON validation, explicit thresholds) to prevent fabricated detection statistics.
- Built a 1024-d qwen embedding + FAISS RAG pipeline with document/page citations and a no-answer path.
- Implemented a 5-tool LangGraph agent with max 6 steps, timeout, tool-error passthrough, and persisted tool traces.
- Delivered 45 pytest tests, frontend production build, and a healthy 3-container Docker Compose stack.
