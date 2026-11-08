# ECE-YOLO 接入验证记录（P3 前置）

> 日期：2026-11-06
> 状态：**已接入业务代码（P3）**；本文件记录接入前的加载验证与兼容层原理。实施结果见 [05-phase-3-report.md](05-phase-3-report.md)。
> 相关设计：[01-architecture-design.md](01-architecture-design.md) §5.1

---

## 1. 收到的资源

| 资源 | 路径 |
|---|---|
| 权重 | `D:\ECE-yolo-project\best.pt`（4.68 MB） |
| 自定义模块 | `D:\yolo11（2）\ultralytics-main\ultralytics\nn\Addmodules\` |
| 训练 yaml | `D:\yolo11（2）\ultralytics-main\yaml\ESPMStem+RepNCSPELAN4_low+Dyhead.yaml` |
| 数据集 yaml | `D:\yolo11（2）\VisDrone VisDrone\date.yaml` |
| 训练代码根 | `D:\yolo11（2）\ultralytics-main`（Ultralytics 8.3.209） |

本机没有原始训练代码的 `Addmodules/` 全部依赖环境；只取以下三个模块用于 ECE-YOLO：

- `ESPMStem.py` → `ESPMStem`
- `RepNCSPELAN4.py` → `RepNCSPELAN4_low` / `RepNCSPELAN4_high`
- `DynamicHead.py` → `DynamicHead`

---

## 2. 模型结构（训练 yaml 摘要）

```yaml
nc: 80                    # 模板值；训练时由 data.yaml 覆盖为 10
backbone:
  - [-1, 1, ESPMStem, [64, 0.75]]
  - [-1, 1, Conv, [128, 3, 2]]
  - [-1, 2, RepNCSPELAN4_low, [256]]
  - [-1, 1, Conv, [256, 3, 2]]
  - [-1, 2, RepNCSPELAN4_low, [512]]
  - [-1, 1, Conv, [512, 3, 2]]
  - [-1, 2, RepNCSPELAN4_low, [512]]
  - [-1, 1, Conv, [1024, 3, 2]]
  - [-1, 2, RepNCSPELAN4_low, [1024]]
  - [-1, 1, SPPF, [1024, 5]]
  - [-1, 2, C2PSA, [1024]]
head:
  - ... RepNCSPELAN4_low ...
  - [[16, 19, 22], 1, DynamicHead, [nc]]
```

`DynamicHead` 内部使用 `DyConv` + `Conv3x3Norm`，其中 `Conv3x3Norm` 依赖
`mmcv.ops.ModulatedDeformConv2d`。

---

## 3. checkpoint 实测元数据

用 `torch.load(..., map_location="cpu", weights_only=False)` 读取：

| 字段 | 值 |
|---|---|
| `model` 类型 | `ultralytics.nn.tasks.DetectionModel` |
| `nc` | **10** |
| `names` | pedestrian, people, bicycle, car, van, truck, tricycle, awning-tricycle, bus, motor |
| `stride` | `[8, 16, 32]` |
| `model.yaml.nc` | 10 |
| `train_args.imgsz` | **640** |
| `train_args.conf` | `None`（训练/验证未指定） |
| `train_args.iou` | **0.7** |
| `train_args.epochs` / `batch` | 400 / 8 |
| `train_metrics` | mAP50 = **0.37453**，mAP50-95 = **0.22325**，precision = 0.48795，recall = 0.36511 |
| checkpoint 日期 | 2025-12-24 |

> 这些指标是 checkpoint 中真实记录的值，不是本项目编造。P4 的 LLM 报告只有在显式传入这些 facts 时才允许引用，并必须标注“来自训练 checkpoint 的验证指标”。

---

## 4. 加载问题与兼容方案

### 4.1 问题 1：缺少 `ultralytics.nn.Addmodules`

`best.pt` 的 pickle 引用了：

```text
ultralytics.nn.Addmodules.ESPMStem.ESPMStem
ultralytics.nn.Addmodules.RepNCSPELAN4.RepNCSPELAN4_low
ultralytics.nn.Addmodules.DynamicHead.DynamicHead
```

当前 `envs/py39` 的 Ultralytics 8.3.209 没有 `Addmodules` 包，直接 `YOLO("best.pt")`
会报 `ModuleNotFoundError`。

**方案**：在导入 checkpoint 之前，按 checkpoint 使用的完整模块路径注册三个类：

```python
pkg = types.ModuleType("ultralytics.nn.Addmodules")
pkg.__path__ = [str(add_dir)]
sys.modules["ultralytics.nn.Addmodules"] = pkg
# 逐个 exec 三个 .py，注册为
# ultralytics.nn.Addmodules.ESPMStem / .RepNCSPELAN4 / .DynamicHead
# 再注入 ultralytics.nn.tasks 的 globals，兼容 parse_model
```

### 4.2 问题 2：缺少 `mmcv.ops.ModulatedDeformConv2d`

`DynamicHead.py` 第 433 行：

```python
from mmcv.ops import ModulatedDeformConv2d
```

本机没有 mmcv，且 mmcv 在 Windows + torch 2.1.2 上通常需要编译。P3 不应为了它破坏 py39。

**方案**：在导入 `DynamicHead` 前注入 `mmcv`/`mmcv.ops`/`mmcv.ops.modulated_deform_conv`
三个模块，用 `torchvision.ops.deform_conv2d` 实现同名类：

```python
class ModulatedDeformConv2d(nn.Module):
    # 参数：in_channels, out_channels, kernel_size, stride, padding,
    #       dilation, groups, deform_groups, bias
    # state_dict 键：conv.weight / conv.bias
    def forward(self, x, offset, mask):
        return deform_conv2d(x, offset, self.weight, self.bias,
                             self.stride, self.padding, self.dilation, mask)
```

**关键细节**：mmcv 的输出尺寸由 `input + stride + padding + dilation` 计算，
但 ECE-YOLO 的 `DyConv` 会把“当前层分辨率”的 offset 传给“低一层分辨率、stride=1”的分支，
导致 offset 比 mmcv 计算的输出大 2 倍。真实 mmcv 会按输出尺寸索引 offset 的左上角切片，
所以兼容层在调用 torchvision 前先裁剪：

```python
out_h = (H + 2*pad - dilation*(k-1) - 1) // stride + 1
offset = offset[:, :, :out_h, :out_w]
mask = mask[:, :, :out_h, :out_w]
```

这与 mmcv 的 `_output_size` 行为一致；不是“随便 resize”。

---

## 5. 冒烟验证结果

命令（临时脚本，未进入业务代码）：

```powershell
cd D:\ECE-yolo-project
.\.venv\Scripts\python.exe backend\logs\probe_ece.py
```

输出摘要：

```text
ultralytics: 8.3.209
nc: 10
names: {0: pedestrian, ..., 9: motor}
stride: tensor([8., 16., 32.])
YOLO loaded
boxes: 32
car    0.8371 [948.4, 590.6, 1012.3, 684.1]
car    0.8018 [870.3, 569.0, 926.2, 662.7]
car    0.7775 [877.5, 705.8, 942.7, 813.2]
...
motor  0.5316 [444.8, 565.2, 499.6, 594.7]
people 0.4691 [868.1, 405.8, 880.6, 434.6]
```

- 设备：CPU
- 图片：`D:\yolo11（2）\VisDrone VisDrone\VisDrone2019-DET-val\images\0000001_02999_d_0000005.jpg`
- 参数：`imgsz=640, conf=0.25, iou=0.7`
- CPU：32 个目标，`inference≈507 ms`（`result.speed`）
- GPU（RTX 2060）：32 个目标，`inference≈104 ms`，`postprocess≈130 ms`；框与 CPU 一致
- 结论：**加载、前向、NMS、类别名、坐标均正常，CPU/GPU 均可用**。

---

## 6. 建议的推理默认值

| 参数 | 建议 | 依据 |
|---|---|---|
| `imgsz` | 640 | checkpoint `train_args.imgsz` |
| `conf` | **0.25** | Ultralytics predict 默认；训练时未指定 |
| `iou` | **0.7** | checkpoint `train_args.iou` |
| `max_det` | 300 | 默认；VisDrone 密集图可适当调大 |
| `device` | `auto` | 有 CUDA 用 `cuda:0`，否则 CPU |

> `conf=0.25` 在 VisDrone 密集小目标场景可能偏保守或偏多，P3 会把它做成配置项，前端可调；不写死在代码里。

---

## 7. P3 实施计划（基于本次验证）

建议新增：

```text
backend/app/algorithms/ece_yolo/
├── __init__.py
├── mmcv_shim.py          # ModulatedDeformConv2d + sys.modules 注入
├── modules.py            # 加载 3 个自定义模块并注册到 ultralytics 命名空间
├── loader.py             # load_ece_yolo(weights, device) -> YOLO
└── detector.py           # BaseDetector 适配器：predict -> list[Detection]
backend/config/models.yaml
backend/tests/test_ece_yolo_loader.py
```

约束：

1. 不修改 `envs/py39` 里的 ultralytics 源码；所有注册在进程内完成。
2. 自定义模块源码不直接复制进仓库，优先从配置的 `ECE_YOLO_SOURCE` 路径加载；若要随项目分发，需保留 AGPL-3.0 许可证与来源说明。
3. 加载器只执行一次，由 `ModelManager` 缓存。
4. 兼容层与真实 mmcv 的数值一致性用固定输入做回归测试；当前未安装 mmcv，先记录为已知差异风险。
5. `best.pt` 被 `.gitignore` 忽略，部署时通过挂载/配置提供，不提交到 Git。

---

## 8. 需要你确认

1. 推理默认值是否用 `conf=0.25`、`iou=0.7`、`imgsz=640`？
2. 是否允许把三个自定义模块复制进项目（保留许可证与来源），还是 P3 运行时从 `D:\yolo11（2）\ultralytics-main` 读取？
3. 提供 2–3 张验收图片（VisDrone 验证图即可），我会在 P3 固定为回归样例。
