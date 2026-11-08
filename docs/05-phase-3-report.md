# 第三阶段实施报告（P3）

> 阶段：P3 ECE-YOLO 推理接入
> 日期：2026-11-06
> 结论：**通过**（真实权重加载、CPU/GPU 推理、结果图、33 条目标明细落库；20 个测试通过）
> 设计：[01-architecture-design.md](01-architecture-design.md) §5
> 前置验证：[03-ece-yolo-integration-notes.md](03-ece-yolo-integration-notes.md)

---

## 1. 本阶段目标

1. 把 ECE-YOLO 三个自定义模块接入项目，不修改 `envs/py39`；
2. 用 `torchvision` 兼容层替代缺失的 `mmcv`，能加载 `best.pt`；
3. `ModelManager` 单例：模型只加载一次、GPU 推理串行、启动预热；
4. `POST /api/v1/detection/predict`：真实推理、写目标明细、类别统计、结果图；
5. `/detection/models`、`/detection/overview`；
6. 健康检查反映模型真实状态；
7. CPU/GPU 测试与真实 HTTP 验收。

---

## 2. 交付文件

```text
backend/app/algorithms/
├── base.py                     # Detection 数据类 + BaseDetector 接口
├── registry.py                 # models.yaml 解析 + 适配器工厂
├── model_manager.py            # 单例、懒加载、推理锁、预热、健康/列表
├── mock_detector.py            # 明确标识的 mock
├── visualize.py                # PIL 画框/标签
└── ece_yolo/
    ├── mmcv_shim.py            # mmcv.ops.ModulatedDeformConv2d 兼容层
    ├── modules.py              # 注册 3 个自定义模块 + patch tasks globals
    ├── loader.py               # YOLO(best.pt) 加载
    ├── detector.py             # BaseDetector 适配器
    └── vendor/                 # 三个逐字复制的自定义模块 + NOTICE

backend/config/models.yaml      # ece-yolo / mock 注册表
backend/app/services/detection_service.py   # run_prediction / overview
backend/app/api/v1/endpoints/detection.py   # predict / models / overview
backend/tests/test_ece_yolo_model.py        # 真实 CPU 推理测试
```

---

## 3. 关键实现

### 3.1 mmcv 兼容层

`DynamicHead` 依赖：

```python
from mmcv.ops import ModulatedDeformConv2d
```

本机没有 mmcv，因此 `mmcv_shim.py` 注入：

```text
mmcv
mmcv.ops
mmcv.ops.modulated_deform_conv
```

`ModulatedDeformConv2d` 保留 `weight` / `bias` 参数名，`forward(x, offset, mask)` 调用
`torchvision.ops.deform_conv2d`。

关键细节：mmcv 的输出尺寸由 `input/stride/padding/dilation` 计算；`DynamicHead` 会把
当前分辨率的 offset 传给低分辨率分支，offset 比输出大。兼容层先裁剪到输出尺寸，再调用
torchvision。与 mmcv 的 `_output_size` 行为一致。

### 3.2 模块注册

`modules.py` 只加载三个文件，不执行上游 `Addmodules/__init__.py`（它会 import 几十个无关模块）：

```text
ultralytics.nn.Addmodules.ESPMStem
ultralytics.nn.Addmodules.RepNCSPELAN4
ultralytics.nn.Addmodules.DynamicHead
```

并按 checkpoint pickle 的完整路径注册到 `sys.modules`，同时注入
`ultralytics.nn.tasks` 的 globals，兼容 `parse_model`。

### 3.3 模型管理

- `ModelManager.configure(settings)` 解析 `models.yaml`，`preload()` 在 lifespan 中加载默认模型；
- `get_spec(name)` 支持 key / display_name，`mock` 模式下强制 mock；
- `get()` 用 `RLock` 保证只加载一次，失败不缓存；
- `predict_sync()` 用独立的 `Lock` 串行 GPU 推理；
- `health()` 返回 `ok / unavailable / not_configured`、loaded、device、mock；
- `list_models()` 返回前端模型选择所需信息；
- `shutdown()` 在应用退出时释放模型。

### 3.4 推理与落库

`DetectionService.run_prediction`：

```text
task.status=running
 → manager.predict_sync(model, BGR image, conf, iou)
 → PIL 画框
 → 保存 results/YYYY/MM/{task_id}.jpg
 → 写 detection_results（每个目标一行）
 → 更新 total_objects / class_statistics / inference_time_ms / result_image_path
 → task.status=success
异常：rollback → task.status=failed + error_message → 抛 AppError
```

`class_statistics` 用 `Counter` 按数量降序；结果图通过 `/static/results/...` 访问。

---

## 4. API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/detection/predict` | 真实 ECE-YOLO 推理 |
| GET | `/api/v1/detection/models` | 模型列表、可用/已加载/设备 |
| GET | `/api/v1/detection/overview` | 任务数/目标数/类别分布 |
| GET | `/api/v1/health` | detector 变为真实状态 |

`predict` 请求（multipart）：

| 字段 | 说明 |
|---|---|
| `file` | JPG/JPEG/PNG，≤20 MB |
| `model_name` | 可选，默认 `ece-yolo`；测试可用 `mock` |
| `conf` | 可选，默认取模型配置 0.25 |
| `iou` | 可选，默认取模型配置 0.7 |

---

## 5. 实测结果

### 5.1 启动与健康检查

```text
detector.status = ok
detector.loaded = true
detector.device = cuda:0
detector.model  = ECE-YOLO
database.status = ok (mysql)
```

启动时完成模型加载 + 一次 dummy warmup，首次真实请求不再承担初始化开销。

### 5.2 真实推理（RTX 2060）

输入：`VisDrone2019-DET-val\images\0000001_02999_d_0000005.jpg`

```text
task_id            = ba0a39dca8794effaeae201c9d84c6c3
status             = success
model              = ECE-YOLO
total_objects      = 33
inference_time_ms  = 296   （预热后首次）
第二次              = 47
class_statistics   = {"motor":17, "car":11, "people":2, "pedestrian":2, "truck":1}
result_image       = /static/results/2026/11/ba0a39dca8794effaeae201c9d84c6c3.jpg
```

首条检测：

```json
{"class_id": 3, "class_name": "car", "confidence": 0.8414, "bbox": [949, 591, 1012, 684]}
```

结果图 HTTP 200，约 871 KB；任务详情返回 33 条 `detections`；删除后
`/overview` 的 `total_tasks/total_objects` 回到 0。

> 加 warmup 之前，首次请求为 1642 ms；warmup 后首次 296 ms、第二次 47 ms。
> `inference_time_ms` 只统计 `detector.predict`，不含上传、绘图、落库。

### 5.3 CPU

`test_ece_yolo_model.py` 在 CPU 上加载同一权重并推理 VisDrone 图，`detections > 0`，
类别名与 bbox 有效。CPU 单次约 507 ms（前期 probe 数据）。

### 5.4 测试与静态检查

```text
pytest:     20 passed in 9.45s
ruff:       All checks passed!
pip check:  No broken requirements found.
```

测试覆盖：

- P1/P2 的 health、错误体、request id、上传/CRUD；
- mock 推理：`is_mock=true`、3 个 mock 目标、结果图落盘、overview；
- 模型列表：ECE-YOLO / mock；
- 未知模型 404；
- 真实 ECE-YOLO CPU 推理（缺权重/样图时 skip）。

---

## 6. 遇到的问题

| 问题 | 原因 | 处理 |
|---|---|---|
| mock 推理返回 200 但 `detections=[]` | 请求内 `task` 对象的关系集合已被 `refresh` 初始化为空，`selectinload` 未覆盖 identity map | `get_task_detail` 改为显式查询 `detection_results` 并赋给 schema，避免依赖缓存关系 |
| 首次真实推理 1642 ms | CUDA/cuDNN 首次初始化 + predictor 首次构建 | `load()` 末尾用 640 dummy 图 warmup；首次降到 296 ms |
| 无 mmcv，`DynamicHead` import 失败 | 训练代码依赖 mmcv | `mmcv_shim` 用 torchvision 实现；注册 `mmcv.ops.modulated_deform_conv` 供 pickle 使用 |
| offset 与 torchvision 输出尺寸不匹配 | mmcv 按输入/stride 定输出，offset 可能更大 | 按 mmcv `_output_size` 裁剪 offset/mask |
| 自定义模块触发大量 ruff 报错 | 逐字复制的第三方代码 | `pyproject.toml` 排除 `vendor/`；不修改源码 |

---

## 7. 验收清单

- [x] `best.pt` 真实加载，CPU/GPU 均可推理
- [x] 不修改 `envs/py39`
- [x] 三个自定义模块已复制进项目并保留 NOTICE / 哈希
- [x] `mmcv` 兼容层可加载 checkpoint，类别名正确（10 类）
- [x] 模型只加载一次，启动预热，推理串行
- [x] `POST /detection/predict` 返回目标框/类别/置信度/统计/结果图
- [x] `detection_results` 每目标一行，任务详情返回 33 条
- [x] 结果图通过 `/static` 访问
- [x] 失败任务标记 `failed` + `error_message`
- [x] `/detection/models`、`/detection/overview` 可用
- [x] `/health` 反映 `ok/loaded/device`
- [x] mock 模式明确 `is_mock=true`
- [x] 20 个测试通过，ruff 通过
- [x] 真实 HTTP + MySQL 端到端通过

---

## 8. 下一阶段（P4）

P4 将实现 LLM 分析报告：

1. `services/llm_service.py`：OpenAI 兼容客户端（超时/重试/JSON mode）；
2. `services/stats.py`：空间统计 facts（密度、3×3 网格、最近邻、边缘、尺寸、置信度）；
3. 分析 Prompt：只允许使用 facts，8 段固定结构，禁止编造；
4. `POST /analysis/{task_id}` / `GET /analysis/{task_id}`；
5. `llm_reports` 落库，报告 Markdown + 结构化 JSON；
6. LLM 失败不落半成品，返回可诊断错误。

**需要你提供**：`LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`（不要发在聊天里，写入本机 `.env`）；以及 Embedding 方案（P5 用）。若暂时没有 Key，P4 可先用 `LLM_MOCK=true` 验证结构，但报告会明确标记 `is_mock=true`。
