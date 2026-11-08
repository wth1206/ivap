# 上传到 GitHub

> 目标：把 IVAP 源码、文档、截图、示例数据上传为一个**可展示、无密钥、可复现**的 GitHub 仓库。
> 建议先建 **Private** 仓库，确认没有密钥后再改 Public。
> 项目根目录：`D:\ECE-yolo-project`

---

## 1. 上传前安全检查

### 1.1 绝对不能提交

| 路径 | 原因 |
|---|---|
| `.env` | 真实 LLM / Embedding Key、数据库密码 |
| `.env.docker` | 真实容器密钥 |
| `.mysql/` | 本地 MySQL 数据 |
| `backend/uploads/` | 用户上传图片 |
| `backend/vector_db/` | 运行时 FAISS 索引 |
| `backend/logs/` | 运行日志、可能含请求信息 |
| `frontend/node_modules/` | 体积巨大 |
| `frontend/dist/` | 构建产物 |
| `.venv/` | Python 虚拟环境 |
| `best.pt` | 模型权重，默认不提交（见第 5 节） |

`.gitignore` 已配置以上规则；`best.pt` 通过 `*.pt` 忽略。

### 1.2 检查命令

```powershell
cd D:\ECE-yolo-project
git status --short
git check-ignore -v .env .env.docker best.pt backend/logs backend/uploads frontend/node_modules frontend/dist
```

预期：`.env`、`.env.docker`、`best.pt` 等显示 ignored。

### 1.3 检查代码中是否硬编码密钥

```powershell
# 只显示文件名，不打印密钥值
Get-ChildItem -Recurse -File -Include *.py,*.js,*.vue,*.yaml,*.yml,*.md |
  Where-Object { $_.FullName -notmatch '\\(node_modules|\.venv|\.mysql|logs|uploads|vector_db)\\' } |
  Select-String -Pattern 'sk-[A-Za-z0-9]{16,}','LLM_API_KEY\s*=\s*[^\s#]' |
  Select-Object Path,LineNumber
```

正常情况下只应命中 `.env`/`.env.docker`（已被忽略），或文档里的示例占位符。

---

## 2. 在 GitHub 创建仓库

1. 打开 <https://github.com/new>；
2. Repository name：`ivap` 或 `intelligent-vision-analysis-platform`；
3. 建议先选 **Private**；
4. **不要**勾选 “Add a README file”“Add .gitignore”“Choose a license”；
5. 创建后记下仓库地址：

```text
https://github.com/<your-github-name>/ivap.git
```

---

## 3. 本地初始化并提交

```powershell
cd D:\ECE-yolo-project

# 只有第一次需要
git init -b main

# 设置提交身份（换成你的 GitHub 名称/邮箱）
git config user.name "Your Name"
git config user.email "you@example.com"

# 查看将要提交的文件
git add .
git status --short

# 确认没有 .env / .env.docker / best.pt / node_modules 后提交
git commit -m "feat: IVAP end-to-end vision analysis platform (P1-P8)"
```

如果 `git status` 里出现 `.env`、`.env.docker`、`best.pt`、`node_modules`，**不要 commit**，先检查 `.gitignore`。

---

## 4. 关联远程仓库并推送

```powershell
git remote add origin https://github.com/<your-github-name>/ivap.git
git push -u origin main
```

### 认证方式

GitHub 已不支持账号密码推送，二选一：

**方式 A：Personal Access Token（HTTPS）**

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)；
2. 生成 token，勾选 `repo`；
3. `git push` 时：
   - Username：你的 GitHub 用户名；
   - Password：粘贴 token（不是账号密码）。

**方式 B：SSH**

```powershell
ssh-keygen -t ed25519 -C "you@example.com"
# 一路回车；然后把 ~/.ssh/id_ed25519.pub 添加到 GitHub → Settings → SSH keys
ssh -T git@github.com
git remote set-url origin git@github.com:<your-github-name>/ivap.git
git push -u origin main
```

如果安装并登录了 GitHub CLI，也可以：

```powershell
gh auth login
gh repo create ivap --private --source=. --remote=origin --push
```

---

## 5. 模型权重 `best.pt` 怎么处理

默认 **不提交**，原因：

- 权重可能来自第三方/课程/比赛，公开再分发需要确认许可；
- GitHub 单文件 100 MB 限制（当前 4.68 MB 可以放，但许可优先）；
- 代码仓库保持轻量。

推荐做法：在 README 写清楚：

```text
将 best.pt 放到项目根目录：
D:\ECE-yolo-project\best.pt
```

如果确认有权公开且希望仓库自带权重：

```powershell
git lfs install
git lfs track "*.pt"
git add .gitattributes
git add -f best.pt
git commit -m "chore: add ECE-YOLO weights via Git LFS"
git push
```

或者把 `best.pt` 放到 GitHub Releases，README 给下载链接；这样不占 Git 历史。

---

## 6. 推荐仓库设置

- Description：

```text
UAV remote-sensing analysis: ECE-YOLO + FastAPI + Vue 3 + RAG + LangGraph Agent + Docker
```

- Topics：

```text
yolo fastapi vue3 rag langgraph faiss docker remote-sensing computer-vision
```

- 首页：README 已包含截图、核心亮点、快速开始、测试结果、文档链接；
- 先 Private 检查一遍，再改 Public；
- 如果代码/权重许可不明确，选择 Private 或补 LICENSE。

---

## 7. 上传后验证

```powershell
# 另找一个目录克隆，模拟别人第一次拿到仓库
cd D:\
git clone https://github.com/<your-github-name>/ivap.git ivap-check
cd ivap-check

# 确认没有密钥和大文件
Get-ChildItem -Recurse -File | Where-Object { $_.Length -gt 5MB } |
  Select-Object FullName,Length
```

然后按 README 的“快速开始”：

```powershell
Copy-Item .env.example .env
# 填 LLM / Embedding / MySQL 配置
```

Docker 路线见 [docs/10-deployment.md](docs/10-deployment.md)。

---

## 8. 常见问题

| 问题 | 处理 |
|---|---|
| `remote origin already exists` | `git remote set-url origin <url>` |
| `Authentication failed` | 用 PAT，不要用账号密码 |
| `rejected: non-fast-forward` | `git pull --rebase origin main` 后再 push |
| `file is 100 MB` | 大文件改用 Git LFS / Release，或加入 `.gitignore` |
| 误提交 `.env` | 立刻删除文件、`git rm --cached .env`、提交；**并立即轮换所有 Key** |
| 图片不显示 | README 使用相对路径 `docs/screenshots/...`，确认文件已提交 |
| 克隆后无法启动 | 检查 `.env`、`best.pt`、MySQL；按 README 逐项来 |

---

## 9. 简历怎么写

项目描述、技术栈、量化结果和面试讲述稿见：

- [简历项目写法](docs/14-resume-bullets.md)
- [开发全流程](docs/12-full-development-record.md)
