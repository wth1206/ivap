# 第二阶段实施报告（P2）

> 阶段：P2 数据库与任务 CRUD
> 日期：2026-11-06
> 结论：**通过**（MySQL 8.0.28 + Alembic + 上传/列表/详情/删除；15 个测试通过）
> 设计：[01-architecture-design.md](01-architecture-design.md) §6–§7
> P1 报告：[02-phase-1-report.md](02-phase-1-report.md)

---

## 1. 本阶段目标

1. 安装 MySQL 8.0，创建 `ivap` 库与专用用户；
2. SQLAlchemy 2.0 ORM：8 张表（任务书 7 张 + `knowledge_chunks`）；
3. Alembic 初始迁移；
4. 图片上传（校验、EXIF 规范化、落盘、URL）；
5. 任务列表/详情/删除 API，统一分页与错误；
6. 数据库健康检查；
7. SQLite 单元测试 + MySQL 实测。

**不包含**：YOLO 推理（P3）、LLM（P4）、RAG（P5）、Agent（P6）。

---

## 2. MySQL 安装（本机）

本机没有管理员权限，因此使用 **MySQL 8.0.28 免安装 ZIP**，不注册 Windows 服务：

| 项 | 值 |
|---|---|
| 版本 | 8.0.28 |
| 安装目录 | `D:\ECE-yolo-project\.mysql\mysql-8.0.28-winx64` |
| 数据目录 | `D:\ECE-yolo-project\.mysql\data` |
| 监听 | `127.0.0.1:3306` |
| 配置文件 | `.mysql\my.ini` |
| 库 | `ivap`，`utf8mb4` / `utf8mb4_unicode_ci` |
| 应用用户 | `ivap`@`127.0.0.1` / `ivap`@`localhost` |
| 凭据 | `.mysql\credentials.txt`（本机，不提交 Git） |
| 启动 | `scripts\mysql_start.cmd`（前台，Ctrl+C 停止） |
| 停止 | `scripts\mysql_stop.cmd` |
| 状态 | `scripts\mysql_status.cmd` |

下载源：阿里云 MySQL 镜像，ZIP 222,021,254 字节，MD5 校验通过。

初始化命令（已执行）：

```powershell
mysqld --defaults-file=D:\ECE-yolo-project\.mysql\my.ini --initialize-insecure --console
```

> 首次初始化时 PowerShell 把 `--defaults-file=(Join-Path ...)` 解析成了错误参数，报
> “Failed to open required defaults file: D:\ECE-yolo-project\”。改为先拼接字符串
> `--defaults-file=$myIni` 后成功。数据目录当时为空，没有残留。

随后用 root 空密码执行：

```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '<random>';
CREATE DATABASE ivap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ivap'@'127.0.0.1' IDENTIFIED BY '<random>';
CREATE USER 'ivap'@'localhost' IDENTIFIED BY '<random>';
GRANT ALL PRIVILEGES ON ivap.* TO 'ivap'@'127.0.0.1';
GRANT ALL PRIVILEGES ON ivap.* TO 'ivap'@'localhost';
FLUSH PRIVILEGES;
```

root 密码与应用密码均为 24 字符随机值，只写入 `.mysql\credentials.txt` 与本机 `.env`。

---

## 3. 数据库设计落地

迁移文件：`backend/alembic/versions/715d6a5194fc_initial_schema.py`
当前版本：`715d6a5194fc (head)`
`alembic check`：**No new upgrade operations detected.**

| 表 | 用途 |
|---|---|
| `users` | 用户与 PBKDF2 密码哈希 |
| `detection_tasks` | 检测任务、原图/结果图路径、模型、状态、类别统计缓存 |
| `detection_results` | 每个目标一行，bbox/置信度/类别 |
| `llm_reports` | LLM 报告 Markdown + 结构化 JSON + token/耗时 |
| `knowledge_documents` | 知识文档元信息、hash、状态、Embedding 信息 |
| `knowledge_chunks` | 切片内容、页码、FAISS id（引用与索引重建） |
| `conversations` | 会话 |
| `chat_messages` | 消息、tool_calls、citations、token_usage |

设计要点：

- MySQL InnoDB / utf8mb4；JSON 列用于统计、结构化报告、引用；
- `detection_tasks` 索引：`created_at`、`(user_id, created_at)`、`status`、`model_name`；
- `detection_results` 索引：`(task_id)`、`(task_id, class_name)`；
- `knowledge_chunks` 唯一约束：`(document_id, chunk_index)`，`faiss_id` 唯一；
- 外键：任务/报告/切片级联删除；用户删除时 `SET NULL`；
- SQLite 兼容：主键用 `BigInteger().with_variant(Integer, "sqlite")`，否则 SQLite 不会自增；
- 时间统一 UTC 存储（naive DATETIME），API 序列化为 `...Z`。

---

## 4. 交付文件

```text
backend/app/
├── db/
│   ├── base.py                 # DeclarativeBase + 命名约定
│   ├── session.py              # 懒加载 engine / SessionLocal / get_db / 健康探针
│   ├── types.py                # BIGINT/INTEGER 变体
│   └── init_db.py              # create_all/drop_all（测试/开发）
├── models/
│   ├── user.py
│   ├── detection.py
│   ├── report.py
│   ├── knowledge.py
│   └── chat.py
├── schemas/detection.py
├── core/security.py            # PBKDF2-SHA256，600k 迭代
├── services/
│   ├── storage.py              # 图片落盘、路径安全、删除、URL
│   └── detection_service.py    # 创建/列表/详情/删除
├── utils/image.py              # 扩展名/magic bytes/Pillow/EXIF/尺寸
├── utils/ids.py
└── api/v1/endpoints/detection.py

backend/alembic.ini
backend/alembic/env.py
backend/alembic/versions/715d6a5194fc_initial_schema.py
backend/tests/test_detection_api.py
backend/tests/test_security.py
scripts/mysql_start.cmd / mysql_stop.cmd / mysql_status.cmd / run_backend.cmd
```

---

## 5. API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/detection/upload` | 上传图片，创建 `pending` 任务（不推理） |
| GET | `/api/v1/detection/tasks` | 分页 + keyword/status/model/time 筛选 |
| GET | `/api/v1/detection/tasks/{task_id}` | 详情（P2 的 detections 为空） |
| DELETE | `/api/v1/detection/tasks/{task_id}` | 级联删除 + 删文件 |
| GET | `/api/v1/health` | 数据库状态变为真实探针 |

上传校验：

- 扩展名 JPG/JPEG/PNG；
- magic bytes（JPEG `FF D8 FF` / PNG 签名）；
- Pillow `verify()` + 重新打开解码；
- 大小上限 `MAX_IMAGE_MB`（默认 20 MB）；
- EXIF 方向转正、转 RGB、统一保存为 JPEG；
- 文件名 UUID，原始名只进 DB；路径穿越拒绝；
- 图片按 `images/YYYY/MM/{uuid}.jpg` 存储。

---

## 6. 实测结果

### 6.1 单元测试（SQLite 临时库）

```text
$ cd backend; ..\.venv\Scripts\python.exe -m pytest -q
...............                                                          [100%]
15 passed in 3.08s
```

覆盖：健康检查、404 统一错误、request id、OpenAPI、上传成功、分页/关键词、错误扩展名、损坏图片、任务不存在、删除文件与行、缺文件 422、密码哈希。

### 6.2 MySQL 真实链路

```text
health:  status=ok, database={'status':'ok','detail':None,'dialect':'mysql'}
upload:  201, task=0aac5247035c4bc591a309a8e895ba9a, status=pending, 800x600
list:    total=1
detail:  200
delete:  200
list_after: total=0
```

`GET /api/v1/health` 的 database 组件从 P1 的 `not_configured` 变为：

```json
{"status": "ok", "detail": null, "dialect": "mysql"}
```

### 6.3 迁移

```text
$ alembic current
715d6a5194fc (head)
$ alembic check
No new upgrade operations detected.
```

`SHOW TABLES` 包含 8 张业务表 + `alembic_version`。

### 6.4 真实 HTTP 端到端（uvicorn + MySQL）

```text
GET  /api/v1/health                 -> status=ok, database=ok, dialect=mysql
POST /api/v1/detection/upload       -> 201, task=57490468..., 640x480
GET  /static/images/2026/11/...jpg  -> 200, 9030 bytes
DELETE /api/v1/detection/tasks/{id} -> {"deleted": true}
GET  /api/v1/detection/tasks        -> total=0
```

验证后已停止 uvicorn；MySQL 仍在后台运行，可用 `scripts\mysql_status.cmd` 检查。

---

## 7. 遇到的问题

| 问题 | 原因 | 处理 |
|---|---|---|
| `mysqld --defaults-file=(Join-Path ...)` 失败 | PowerShell 参数表达式被拆分 | 先拼字符串，再作为单个参数传入 |
| 首次初始化报 “Failed to open required defaults file: D:\ECE-yolo-project\” | 同上 | 修正后初始化成功，data 目录无残留 |
| ruff 报自定义模块大量问题 | 三个模块是逐字复制的第三方代码 | `pyproject.toml` 排除 `backend/app/algorithms/ece_yolo/vendor`；不修改源码 |
| ruff 报 Alembic 自动生成迁移的导入顺序 | 生成代码 | 排除 `backend/alembic/versions` |
| SQLite 下 BigInteger 主键不自增 | SQLite 只有 INTEGER PRIMARY KEY 自增 | `bigint_pk()` 使用 `BigInteger().with_variant(Integer, "sqlite")` |

---

## 8. 验收清单

- [x] MySQL 8.0.28 安装、初始化、仅监听 127.0.0.1
- [x] `ivap` 库、专用用户、utf8mb4
- [x] 7 张任务书表 + `knowledge_chunks`
- [x] Alembic 初始迁移 + `upgrade head` + `check` 无漂移
- [x] 图片扩展名/magic/Pillow/大小/EXIF 校验
- [x] 图片落盘 + DB 相对路径 + `/static` URL
- [x] 上传、分页列表、详情、删除（级联 + 文件）
- [x] 任务状态 `pending`，不伪造检测结果
- [x] 数据库健康检查（MySQL ok / 断开 degraded）
- [x] 密码 PBKDF2-SHA256 + 盐 + 600k 迭代
- [x] 15 个 pytest 通过
- [x] ruff 全部通过
- [x] MySQL 真实链路实测通过

---

## 9. 下一阶段（P3）

P3 将：

1. 把 ECE-YOLO 三个模块 + mmcv 兼容层封装到 `backend/app/algorithms/ece_yolo/`；
2. `ModelManager` 单例加载 `best.pt`，`imgsz=640 / conf=0.25 / iou=0.7`；
3. 实现 `POST /api/v1/detection/predict`，替换/复用 P2 的上传落盘；
4. 写入 `detection_results`、生成结果图、统计类别；
5. 前端可用的 `/detection/models`、`/detection/overview`（P3/P7）；
6. 用 VisDrone 验证图做真实推理回归，CPU/GPU 均验证。

已知风险：torchvision 兼容层与真实 mmcv 的数值一致性，P3 用固定输入做对照测试。
