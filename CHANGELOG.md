# Changelog

## [0.1.0] - 2026-11-08

### P1 — 工程骨架

- FastAPI app factory、lifespan、CORS、静态目录、健康检查；
- 统一配置、日志、异常、request_id、中间件；
- pytest 测试基线。

### P2 — MySQL 与任务

- MySQL 8.0.28、SQLAlchemy 2、Alembic；
- 8 张表与任务 CRUD；
- 上传类型 / magic bytes / 大小 / 路径校验。

### P3 — ECE-YOLO

- 三个自定义模块（ESPMStem / RepNCSPELAN4 / DynamicHead）接入；
- mmcv-free `deform_conv2d` 兼容层；
- 真实推理、结果图、类别统计、任务持久化；warmup。

### P4 — LLM 分析

- `LLMService.chat_text/chat_json`；
- facts-only 8 段报告、JSON 校验、阈值注入、Mock 标记。

### P5 — RAG

- PDF/DOCX/TXT 解析、清洗、切分；
- qwen3.7 1024 维 Embedding、FAISS 持久化；
- 检索、问答、`[S1]` 引用、`no_answer`。

### P6 — LangGraph Agent

- 5 工具、最多 6 轮、180s 超时；
- 工具参数校验、错误回传、工具轨迹；
- 会话 / 消息 / 引用持久化。

### P7 — Vue 3 前端

- 6 页面、Element Plus、ECharts、Markdown/DOMPurify；
- Vite 代理、Axios 统一错误；
- 生产构建、Chrome 冒烟。

### P8 — Docker / 部署

- Docker Desktop 4.98 + WSL2 3.0.1；
- MySQL + FastAPI + Nginx 三容器；
- CPU 默认、GPU overlay、数据卷持久化；
- 45 个后端测试、部署指南、归档、简历材料。
