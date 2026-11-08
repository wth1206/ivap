# 部署指南（Docker Compose）

> 适用：Windows 10/11 + WSL2 + Docker Desktop，或 Linux + Docker Engine。
> 目标：一条命令启动 MySQL 8.0、FastAPI 后端、Nginx 前端。

---

## 1. 架构

```text
浏览器 :8080
   │
   ▼
ivap-frontend (Nginx)
   ├── /            → Vue dist（SPA）
   ├── /api/        → ivap-backend:8000
   └── /static/     → ivap-backend:8000
                         │
                         ├── MySQL 8.0（内部 3306）
                         ├── ECE-YOLO best.pt
                         ├── SQLite?  不使用
                         ├── uploads / vector_db / logs 命名卷
                         └── LLM + Embedding（外部 HTTPS）
```

只有 `frontend:80`、`backend:8000`、`mysql:3307` 映射到宿主机；容器之间通过 Compose 网络访问。

---

## 2. Windows 安装 Docker Desktop + WSL2

### 2.1 前置检查

- Windows 10 22H2（build 19045）或 Windows 11 23H2+；
- BIOS 已开启 Intel VT-x / AMD-V；
- 至少 8 GB 内存；
- 建议至少 30 GB 空闲磁盘（镜像 + 模型 + 数据卷）。

管理员 PowerShell：

```powershell
# 启用 WSL2 所需功能（需要重启）
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# 重启后
wsl --update
wsl --set-default-version 2
wsl --version
```

`wsl --version` 需要显示 2.1.5 或更高；如果仍显示帮助，说明还是旧版 inbox WSL，执行：

```powershell
winget install --id Microsoft.WSL -e --accept-package-agreements --accept-source-agreements
```

### 2.2 安装 Docker Desktop 到 D 盘

官方安装器支持：

- `--installation-dir=<path>`：程序安装目录；
- `--wsl-default-data-root=<path>`：WSL 数据盘（镜像、容器层）。

本项目使用：

```powershell
$exe = 'D:\ECE-yolo-project\.cache\docker\Docker Desktop_4.98.0_Machine_X64_exe_en-US.exe'
Start-Process $exe -Verb RunAs -Wait -ArgumentList @(
  'install',
  '--quiet',
  '--accept-license',
  '--backend=wsl-2',
  '--installation-dir=D:\Docker',
  '--wsl-default-data-root=D:\DockerData',
  '--no-windows-containers',
  '--always-run-service'
)
```

> 如果安装包不在 `.cache`，可先从 <https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe> 下载，并核对 SHA256。

安装完成后重启 Windows，启动 Docker Desktop，接受许可协议。

### 2.3 验证

```powershell
docker version
docker compose version
wsl --list --verbose
docker run --rm hello-world
```

Docker Desktop → Settings → Resources → Advanced 中确认 **Disk image location** 位于 `D:\DockerData`。

---

## 3. 配置环境变量

复制示例：

```powershell
Copy-Item .env.docker.example .env.docker
notepad .env.docker
```

必须填写：

| 变量 | 说明 |
|---|---|
| `MYSQL_ROOT_PASSWORD` | MySQL root 密码，自己生成 |
| `MYSQL_PASSWORD` | 应用用户 `ivap` 密码 |
| `SECRET_KEY` | 长随机字符串 |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | 真实 LLM |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL` | 真实 Embedding |
| `EMBEDDING_DIM` | 必须与模型输出一致（当前 1024） |

`ENV_FILE=.env.docker` 已写在示例中，Compose 会把它作为 backend 的 `env_file`。

> 不要把 `.env.docker` 提交到 Git；`.gitignore` 已忽略。

---

## 4. 启动

### 4.1 CPU（默认）

```powershell
docker compose --env-file .env.docker up -d --build
```

或：

```powershell
scripts\docker_up.cmd
```

首次构建会下载 PyTorch CPU 轮子、Python 依赖和 Node 依赖，约 10–20 分钟。

### 4.2 NVIDIA GPU（RTX 2060）

前提：

- NVIDIA 驱动已安装，`nvidia-smi` 正常；
- Docker Desktop 使用 WSL2 后端并启用 GPU；
- 能运行 `docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi`。

构建并启动：

```powershell
docker compose --env-file .env.docker -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```

GPU overlay 会把 PyTorch 换成 `2.1.2+cu118`，并申请 NVIDIA GPU。

### 4.3 访问

| 地址 | 用途 |
|---|---|
| <http://localhost:8080> | 前端 |
| <http://localhost:8000/docs> | Swagger |
| <http://localhost:8000/api/v1/health> | 健康检查 |
| `localhost:3307` | MySQL（调试用） |

---

## 5. 运行与排障

```powershell
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f mysql
```

- 后端启动时会自动执行 `alembic upgrade head`；
- `MODEL_PRELOAD=true`，首次健康检查有 180s `start_period`；
- 单 worker：模型/FAISS 在进程内，不要扩成多 worker；
- 上传图片、FAISS 索引、日志分别落在 `uploads`、`vector_db`、`logs` 命名卷；
- MySQL 数据在 `mysql_data` 命名卷。

停止（保留数据）：

```powershell
docker compose down
```

清空数据（**不可恢复**）：

```powershell
docker compose down -v
```

---

## 6. 数据备份

```powershell
# MySQL
docker compose exec mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" ivap' > backup-ivap.sql

# 上传/向量/日志卷
docker run --rm -v ivap_uploads:/data -v ${PWD}:/backup alpine tar czf /backup/uploads.tar.gz -C /data .
docker run --rm -v ivap_vector_db:/data -v ${PWD}:/backup alpine tar czf /backup/vector_db.tar.gz -C /data .
```

卷名前缀由 Compose 项目名决定（默认 `ivap_`），用 `docker volume ls` 确认。

---

## 7. 常见问题

| 现象 | 处理 |
|---|---|
| `wsl --version` 显示帮助 | 旧版 WSL；`winget install Microsoft.WSL` 后重启 |
| `WSL 2 installation is incomplete` | 安装 WSL2 内核更新；`wsl --update` |
| `0x80370102` | BIOS 虚拟化未开，或 VirtualMachinePlatform 未启用 |
| Docker Desktop 一直 Starting | 重启 Docker Desktop；`wsl --shutdown`；检查 `com.docker.service` |
| backend 健康检查失败 | `docker compose logs backend`；常见为 `.env.docker` 缺 LLM/DB 变量 |
| MySQL 认证失败 | 改密码后必须 `docker compose down -v` 重建数据卷，或手动改 MySQL 用户 |
| 前端 502 | backend 还没 healthy；等模型加载完成 |
| 上传大图 413 | Nginx `client_max_body_size` 已设 50m；检查后端 `MAX_IMAGE_MB` |
| GPU 不可用 | 用 CPU compose；或安装 NVIDIA 驱动 + GPU overlay，检查 `nvidia-smi` |
| 构建卡在 pip | 配置国内 PyPI 镜像或代理；不要改 torch 版本 |

---

## 8. 本机实测（2026-11-07）

| 项 | 实测 |
|---|---|
| Docker Desktop | 4.98.0，安装到 `D:\Docker` |
| WSL | 3.0.1.0，内核 6.18.40.1-1；默认版本 2 |
| WSL 数据盘 | `D:\DockerData` |
| `.wslconfig` | 8 GB / 8 核 / 2 GB swap |
| 镜像 | backend 2.83 GB、frontend 76.2 MB、mysql 693 MB |
| 容器常驻内存 | backend 约 350–450 MB；MySQL 约 360–405 MB；Nginx 8–10 MB |
| Docker VM 空闲 | 约 1.7 GB |
| 宿主机空闲 | 拉起整套后约 4.3 GB |
| 真实检测（CPU） | 32 个目标，473 ms |
| 分析报告 | 42.96 s，2600 prompt + 1509 completion tokens |
| 前端 | <http://localhost:8080>，Nginx `/api`、`/static` 反代正常 |
| 数据持久化 | `docker compose down` 后重新 `up -d`，任务/报告/文档仍在 |

三容器均 `healthy`：

```text
ivap-mysql     mysql:8.0.28        localhost:3307
ivap-backend   ivap-backend:latest localhost:8000
ivap-frontend  ivap-frontend:latest localhost:8080
```

---

## 9. 国内网络镜像（本机实际使用）

Docker Hub 直连超时，本机做了三处处理：

1. Docker Desktop 的 `daemon.json` 增加 registry mirror：
   ```json
   {
     "registry-mirrors": ["https://docker.1panel.live"]
   }
   ```
2. MySQL 镜像层从 1panel 拉取超时，改用 DaoCloud 镜像后本地打 tag：
   ```powershell
   docker pull docker.m.daocloud.io/library/mysql:8.0.28
   docker tag docker.m.daocloud.io/library/mysql:8.0.28 mysql:8.0.28
   ```
3. PyTorch 官方源下载卡住，改用阿里云 wheel；PyPI 用清华源：
   ```dotenv
   PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
   TORCH_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cpu/torch-2.1.2%2Bcpu-cp39-cp39-linux_x86_64.whl
   TORCHVISION_WHEEL_URL=https://mirrors.aliyun.com/pytorch-wheels/cpu/torchvision-0.16.2%2Bcpu-cp39-cp39-linux_x86_64.whl
   ```

> 如果不在国内，把上述 URL 换回官方 PyPI / `download.pytorch.org` 即可；Dockerfile 和 Compose 都支持通过 build args 覆盖。

Dockerfile 额外固定了与宿主环境一致的版本，避免 `ultralytics` 把 NumPy 升到 2.x：

```text
numpy==1.26.4
opencv-python==4.11.0.86
ultralytics==8.3.209
```

---

## 10. 生产化建议

- 为 `.env.docker` 使用强密码，不要把端口 3307/8000 暴露到公网；
- 在 Nginx 前加 HTTPS（证书挂载 + 443 server）；
- 限制 `/docs` 访问或关闭；
- 配置日志轮转和备份；
- 本项目的 Agent/模型状态在单进程内，水平扩展前需要把 FAISS 与模型服务拆分。
