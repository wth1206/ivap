# 第一阶段实施报告（P1）

> 阶段：P1 项目初始化与后端骨架
> 日期：2026-11-06
> 结论：**通过**（健康检查、Swagger、统一错误、日志、6 个测试、ruff 全部通过）
> 详细设计：[01-architecture-design.md](01-architecture-design.md)

---

## 1. 本阶段目标

交付一个可启动、可测试、可观测的 FastAPI 后端骨架：

- 创建项目目录、虚拟环境、依赖清单；
- 应用工厂、CORS、静态目录、lifespan；
- `GET /api/v1/health` 健康检查；
- 配置系统（`.env` / 环境变量 / 路径解析）；
- 控制台 + 滚动文件日志，日志带 `request_id`；
- 统一异常与错误响应；
- RequestID / 耗时中间件；
- pytest + TestClient；
- `.gitignore`、`.env.example`、README、目录骨架。

**不包含**：数据库连接、模型加载、LLM、RAG、Agent、前端页面。

---

## 2. 交付文件

```text
D:\ECE-yolo-project\
├── .gitignore
├── .env.example
├── README.md
├── requirements.txt
├── requirements-vision.txt
├── requirements-dev.txt
├── requirements.lock.txt          # venv 内新增依赖的精确版本（48 项）
├── pyproject.toml                 # ruff 配置
├── best.pt                        # ECE-YOLO 权重（本地文件，git 忽略）
├── frontend/README.md             # P7 前端占位
├── docs/
│   ├── 01-architecture-design.md
│   └── 02-phase-1-report.md       # 本文件
└── backend/
    ├── app/
    │   ├── main.py
    │   ├── api/v1/router.py
    │   ├── api/v1/endpoints/health.py
    │   ├── core/{config,logging,exceptions,middleware}.py
    │   ├── schemas/{common,health}.py
    │   ├── utils/time.py
    │   ├── services/ models/ db/ algorithms/ rag/ agents/   # 占位包
    │   └── __init__.py
    ├── tests/{conftest.py,test_health.py,__init__.py}
    ├── pytest.ini
    ├── uploads/.gitkeep
    ├── vector_db/.gitkeep
    └── logs/                     # 运行时生成
```

关键实现：

| 文件 | 内容 |
|---|---|
| `core/config.py` | Pydantic Settings v2；`.env` 绝对路径；相对路径按项目根解析；`SecretStr` 保护密钥 |
| `core/logging.py` | console + RotatingFileHandler（10 MB × 5）；ContextVar 注入 `request_id` |
| `core/exceptions.py` | `AppError` + 422/HTTP/500 统一处理器；错误体含 `code/message/details/request_id` |
| `core/middleware.py` | 纯 ASGI 中间件；透传/生成 `X-Request-ID`；`X-Process-Time-Ms`；访问日志 |
| `api/v1/endpoints/health.py` | 数据库/模型/LLM/向量库状态；P1 为 `not_configured` |
| `main.py` | 应用工厂、CORS、异常注册、`/static` 挂载、`/`、`/health` 别名 |
| `tests/test_health.py` | 6 个契约测试 |

---

## 3. 环境与依赖

### 3.1 创建方式

```powershell
D:\Anaconda\envs\py39\python.exe -m venv D:\ECE-yolo-project\.venv --system-site-packages
```

- venv 复用 `envs/py39` 的 torch / torchvision / OpenCV / Ultralytics；
- 新依赖只写入 `.venv\Lib\site-packages`，**未修改** `envs/py39`；
- 本机 PowerShell 5.1 禁止 `.ps1`，全程直接调用 `.venv\Scripts\python.exe`。

### 3.2 实测版本

| 组件 | 版本 |
|---|---|
| Python | 3.9.21 |
| torch / torchvision | 2.1.2+cu118 / 0.16.2+cu118 |
| CUDA | `torch.cuda.is_available() = True` |
| GPU | RTX 2060 6 GB |
| OpenCV / Ultralytics | 4.11.0 / 8.3.209 |
| FastAPI / Pydantic | 0.115.12 / 2.11.2（复用 py39） |
| SQLAlchemy / PyMySQL | 2.0.57 / 1.2.3 |
| LangChain / LangGraph | 0.3.30 / 0.3.34 |
| FAISS | 1.9.0（Windows wheel，已实测 add/search） |
| PyMuPDF / python-docx | 1.26.5 / 1.2.0 |
| pytest / ruff | 8.4.2 / 0.17.4 |
| pip | 26.0.1 |

`requirements.lock.txt` 只记录 venv 本地新增的 48 个包；torch/vision 等复用包见 `requirements-vision.txt` 与本表。

---

## 4. 执行命令与实测结果

### 4.1 安装

```powershell
D:\ECE-yolo-project\.venv\Scripts\python.exe -m pip install --upgrade pip
D:\ECE-yolo-project\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

实际使用了清华镜像加速（仅命令行参数，未写入仓库）：

```powershell
-i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4.2 验证输出

```text
$ .\.venv\Scripts\python.exe -m pip check
No broken requirements found.

$ cd backend; ..\.venv\Scripts\python.exe -m pytest -q
......                                                                   [100%]
6 passed in 0.11s

$ ..\.venv\Scripts\ruff.exe check .
All checks passed!
```

### 4.3 HTTP 实测

```text
GET http://127.0.0.1:8000/api/v1/health
status = 200
X-Request-ID = verify-p1-001（透传成功）
X-Process-Time-Ms = 18.38
```

响应（截取）：

```json
{
  "status": "ok",
  "app": "Intelligent Vision Analysis Platform",
  "version": "0.1.0",
  "environment": "development",
  "components": {
    "database": {"status": "not_configured", "detail": "P2 接入数据库"},
    "detector": {"status": "not_configured", "detail": "P3 接入模型", "model": "ece-yolo", "loaded": false},
    "llm": {"configured": false},
    "vector_store": {"status": "not_configured", "detail": "P5 接入知识库"}
  }
}
```

其他：

```text
GET /docs           -> 200
GET /openapi.json   -> 200；paths 包含 /api/v1/health
GET /               -> {"name": ..., "docs": "/docs", "health": "/api/v1/health"}
GET /health         -> 200（容器探针别名）
GET /api/v1/nope    -> 404
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Not Found",
    "details": null,
    "request_id": "89de776a85f0465bb2712a951f130658"
  }
}
```

日志实测（`backend/logs/app.log`）：

```text
2026-11-06 20:56:12 | INFO | - | app.main | Starting Intelligent Vision Analysis Platform v0.1.0 (env=development)
2026-11-06 20:56:18 | INFO | verify-p1-001 | app.access | GET /api/v1/health -> 200 (18.50 ms) client=127.0.0.1
```

> 控制台/`Invoke-WebRequest` 显示中文可能为乱码，这是 PowerShell 5.1 用 GBK 解码 UTF-8 的显示问题；响应的 `Content-Type: application/json` 与 httpx 解析结果均为正确 UTF-8（`\u63a5\u5165...`），不是接口缺陷。

---

## 5. 遇到的问题与处理

| 问题 | 原因 | 处理 |
|---|---|---|
| `pip install` 从 pypi.org 下载停在 PyMuPDF 18.7 MB | 网络极慢（30–60 KB/s） | 改用清华镜像，速度恢复到 30+ MB/s；镜像只作为命令参数，不写入仓库 |
| `greenlet 3.2.5` 源码构建失败：需要 MSVC 14.0 | 该版本没有 cp39 Windows wheel | 在 `requirements.txt` 固定 `greenlet==3.1.1`（有 cp39 win_amd64 wheel），并加注释 |
| `python -m ruff` 报 `FileNotFoundError: .venv\Scripts\ruff.exe` | ruff 原先由 py39 提供，模块入口找不到 venv 的 exe | 在 venv 内单独安装 ruff 0.17.4，生成 `.venv\Scripts\ruff.exe` |
| requirements 文件被 pip 按 GBK 解码失败 | 文件含中文注释，pip 在无 BOM 时用系统 locale 解码 | requirements 文件改为 **纯 ASCII 注释**；中文说明放 README/docs |
| PowerShell 中中文响应显示乱码 | PS 5.1 按 GBK 解码无 charset 的响应 | 用 httpx/浏览器验证为正确 UTF-8；不影响实际接口 |
| 首次 `Tee-Object` 失败 | `backend/logs` 尚未创建 | 先创建日志目录；应用启动时也会自动创建 |

---

## 6. 验收清单

- [x] `.venv` 创建成功，py39 未被修改（新依赖仅进 venv）
- [x] `torch / cv2 / ultralytics` 在 venv 中可用，CUDA=True
- [x] `pip check` 无 broken requirements
- [x] uvicorn 可启动；`/api/v1/health`、`/health`、`/docs`、`/openapi.json` 可访问
- [x] 日志文件生成，访问日志含 `request_id` 与耗时
- [x] 404 使用统一错误体，`request_id` 与响应头一致
- [x] `X-Request-ID` 可透传，`X-Process-Time-Ms` 存在
- [x] `.env.example` 覆盖全部配置，仓库无真实密钥
- [x] pytest 6/6 通过
- [x] ruff 全部通过
- [x] README 启动命令可复现

---

## 7. P3 前置进展：ECE-YOLO 权重（当晚补充）

P1 验收后收到自定义模块与训练配置，已追加完成一次独立验证（尚未接入业务代码）：

- `best.pt`：Ultralytics checkpoint，`nc=10`，VisDrone 10 类，`stride=[8,16,32]`；
- 训练参数：`imgsz=640`、`conf=None`、`iou=0.7`；
- 自定义模块：`ESPMStem`、`RepNCSPELAN4_low`、`DynamicHead`；
- `DynamicHead` 依赖 `mmcv.ops.ModulatedDeformConv2d`；本机无 mmcv，使用 `torchvision.ops.deform_conv2d` 做进程内兼容层；
- CPU 冒烟结果：VisDrone 验证图检出 32 个目标（car/motor/people 等），坐标与置信度正常；
- 尚未与真实 mmcv 做逐层数值对比，P3 会补回归测试。

详见 [ECE-YOLO 接入验证记录](03-ece-yolo-integration-notes.md)。

---

## 8. 启动与回归命令

```powershell
cd D:\ECE-yolo-project
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# 另开终端
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health | ConvertTo-Json -Depth 5
Start-Process http://127.0.0.1:8000/docs

# 测试
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\ruff.exe check .
```

---

## 9. 下一阶段（P2）准备

P2 需要先确定数据库方案：

- **推荐**：安装 MySQL 8.0，创建 `ivap` 库与专用用户；
- **备选**：先用 SQLite 开发（`DATABASE_URL` 已可配置），P2 验收前切 MySQL。

P2 将交付：7 张业务表 + `knowledge_chunks`、Alembic 迁移、Session 依赖、图片上传、任务列表/详情/删除、统一分页。
