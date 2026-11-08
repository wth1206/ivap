# 归档与交接说明

> 归档时间：2026-11-08
> 项目状态：P1–P8 完成
> 全流程记录：[12-full-development-record.md](12-full-development-record.md)
> GitHub 上传：[GITHUB_UPLOAD.md](../GITHUB_UPLOAD.md)
> 简历写法：[14-resume-bullets.md](14-resume-bullets.md)

---

## 1. 归档包

| 项 | 值 |
|---|---|
| 文件 | `archive/IVAP-source-20261108.zip` |
| 文件数 / 大小 | 见 `archive/IVAP-source-20261108-manifest.txt` |
| SHA256 | 见 `archive/IVAP-source-20261108.sha256.txt` |
| 清单 | `archive/IVAP-source-20261108-manifest.txt` |
| 校验文件 | `archive/IVAP-source-20261108.sha256.txt` |

> 该 zip 仅用于本地交接/备份，不提交 GitHub；可在项目根目录运行 `.\.venv\Scripts\python.exe scripts\archive_project.py` 重新生成。

校验：

```powershell
Get-FileHash archive\IVAP-source-20261108.zip -Algorithm SHA256
Get-Content archive\IVAP-source-20261108.sha256.txt
```

### 包含

- `backend/` 源码、迁移、配置、测试；
- `frontend/` 源码、Nginx 配置、Dockerfile；
- `docs/` 全部文档与截图；
- `samples/` 示例图片与 3 份知识文档；
- `scripts/` 启停与归档脚本；
- `docker-compose.yml`、GPU overlay、`.env.example`、`.env.docker.example`；
- `best.pt`（私有交接用；GitHub 默认不提交）。

### 不包含

- `.env`、`.env.docker`（真实密钥）；
- `.venv/`、`.mysql/`；
- `backend/uploads/`、`backend/vector_db/`、`backend/logs/`；
- `frontend/node_modules/`、`frontend/dist/`；
- 运行时 SQLite/日志/缓存。

---

## 2. 仓库结构

```text
ivap/
├── backend/              FastAPI + SQLAlchemy + ECE-YOLO + RAG + Agent
├── frontend/             Vue 3 六页面
├── docs/                 架构、P1–P8 报告、部署、全流程、简历
├── samples/              示例图片与知识文档
├── scripts/              MySQL/后端/前端/Docker/归档
├── archive/              源码 zip（不提交 Git）
├── docker-compose.yml
├── docker-compose.gpu.yml
├── GITHUB_UPLOAD.md
├── README.md
└── best.pt               本地权重（gitignore）
```

---

## 3. 环境要求

| 组件 | 要求 |
|---|---|
| Python | 3.9.x |
| Node.js | 20+（本机 24.21） |
| MySQL | 8.0 |
| Docker | Docker Desktop 4.98 + WSL2（可选） |
| 浏览器 | Chrome / Edge |

本机已验证：

```text
Python 3.9.21
FastAPI 0.115.12
PyTorch 2.1.2+cu118 / CPU 2.1.2+cpu
Ultralytics 8.3.209
Vue 3.5.13 / Vite 6.0.7
MySQL 8.0.28
Docker Desktop 4.98 / Compose v5.6.1
```

---

## 4. 本地运行

```powershell
cd D:\ECE-yolo-project

# 1. 本机 MySQL（保持窗口）
scripts\mysql_start.cmd

# 2. 本机后端（新窗口）
scripts\run_backend.cmd

# 3. 本机前端（新窗口）
scripts\run_frontend.cmd
```

- 后端：<http://127.0.0.1:8000/docs>
- 前端：<http://127.0.0.1:5173>

> 前端已配置 `strictPort=true`，固定 5173，不会因占用自动漂移。
> 本机后端与 Docker 后端不能同时占用 8000。

---

## 5. Docker 运行

```powershell
Copy-Item .env.docker.example .env.docker
# 填写 MySQL / LLM / Embedding 密钥
docker compose --env-file .env.docker up -d --build
```

- 前端：<http://localhost:8080>
- Swagger：<http://localhost:8000/docs>
- MySQL：`localhost:3307`
- 停止：`scripts\docker_down.cmd`

详见 [10-deployment.md](10-deployment.md)。

---

## 6. 密钥与数据

### 必须自己创建

```powershell
Copy-Item .env.example .env
```

填写：

- `DATABASE_URL`
- `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL`
- `EMBEDDING_DIM=1024`
- `SECRET_KEY`

### 数据位置

| 数据 | 位置 |
|---|---|
| 本机 MySQL | `.mysql/data` |
| 上传图片 | `backend/uploads` |
| 结果图 | `backend/uploads/results` |
| FAISS | `backend/vector_db` |
| 日志 | `backend/logs` |
| Docker 数据 | `Docker volumes: ivap_*` |
| Docker WSL 数据盘 | `D:\DockerData` |

备份前先停止写入；Docker 备份命令见部署指南。

---

## 7. 归档时的运行状态

```text
本机 MySQL 3306：运行
本机后端 8000：运行（CUDA，ECE-YOLO 已加载）
本机前端 5173：未运行
Docker 栈：已停止（数据卷保留）
```

这与代码归档无关；按第 4/5 节任意选择一种方式启动即可。

---

## 8. 交付清单

- [x] 源码、文档、示例、归档包
- [x] `.env.example` / `.env.docker.example`
- [x] 本地启动脚本
- [x] Docker Compose + Nginx + GPU overlay
- [x] 45 个后端测试
- [x] 前端生产构建
- [x] GitHub 上传步骤
- [x] 简历项目写法与面试讲稿
- [x] 已知限制说明

---

## 9. 后续问题

如果继续问这个项目，建议按以下顺序：

1. **GitHub**：仓库建好后，把真实 URL 填入 README 和简历；
2. **简历**：从 `14-resume-bullets.md` 选 3–4 条，按目标岗位调整；
3. **面试**：重点准备 ECE-YOLO 兼容层、facts-only 报告、RAG 引用、Agent 工具失败处理；
4. **运行**：本地和 Docker 二选一，不要同时占用 8000；
5. **扩展**：鉴权、模型服务拆分、GPU overlay、OCR、压测。
