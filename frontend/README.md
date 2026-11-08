# IVAP Frontend

基于 **Vue 3 + Vite 6 + Element Plus + Pinia + ECharts** 的单页应用。

## 页面

| 路由 | 页面 |
|---|---|
| `/` | 系统首页 |
| `/detect` | 图像检测 |
| `/analysis` | 智能分析 |
| `/knowledge` | 知识库 |
| `/agent` | Agent 对话 |
| `/history` | 历史任务 |

## 开发

后端需先启动在 `http://127.0.0.1:8000`（Vite 已配置 `/api` 与 `/static` 代理）。

```powershell
cd D:\ECE-yolo-project\frontend
D:\nodejs\npm.cmd install --registry=https://registry.npmmirror.com
D:\nodejs\npm.cmd run dev
```

打开 <http://127.0.0.1:5173>。

> 本机 PowerShell 禁止 `.ps1`，所以使用 `npm.cmd` 而不是 `npm`。

## 构建

```powershell
D:\nodejs\npm.cmd run build
```

产物在 `dist/`，生产环境由 Nginx 托管，并把 `/api`、`/static` 反代到 FastAPI。

## 结构

```text
src/
├── api/          # Axios 封装：http / detection / analysis / knowledge / chat
├── components/   # 布局、上传、检测查看器、图表、Markdown、引用、工具轨迹
├── router/       # 6 个页面路由
├── stores/       # app / detection / knowledge / chat
├── views/        # 6 个页面
├── utils/        # 时间、状态、路径格式化
└── assets/styles # 全局样式
```

## 说明

- Markdown 回答使用 `markdown-it` 渲染，并经 `DOMPurify` 清洗后输出。
- 检测结果图由后端绘制，前端通过 `/static` 加载。
- Mock 检测/报告会在页面显示醒目提示，不会冒充真实结果。
- UI 冒烟脚本：`scripts/e2e-smoke.mjs`、`scripts/chat-smoke.mjs`（需要 Chrome + puppeteer-core）。
