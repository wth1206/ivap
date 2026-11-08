# 第四阶段实施报告（P4）

> 阶段：P4 LLM 智能分析报告
> 日期：2026-11-06
> 结论：**通过**（真实 LLM 生成 8 段报告、数字与 Python facts 一致、报告落库；33 个测试通过）
> 设计：[01-architecture-design.md](01-architecture-design.md) §5.4
> 前置：[05-phase-3-report.md](05-phase-3-report.md)

---

## 1. 本阶段目标

1. Python 计算空间/密度/尺寸/置信度 facts；
2. OpenAI 兼容 LLM 客户端（超时、重试、JSON mode、错误映射）；
3. 8 段固定结构报告，禁止 LLM 编造数量/mAP；
4. `POST /analysis/{task_id}` / `GET /analysis/{task_id}`；
5. `llm_reports` 落库（Markdown + 结构化 JSON + token/耗时）；
6. Mock 模式明确标识；
7. 真实 LLM + 真实检测任务验收。

---

## 2. 交付文件

```text
backend/app/services/
├── stats.py              # 纯 Python facts：密度/3×3 网格/最近邻/边缘/尺寸/置信度/重叠
├── llm_service.py        # AsyncOpenAI 客户端 + JSON 提取 + 错误映射
└── analysis_service.py   # Prompt、facts、8 段校验、Mock、落库、查询

backend/app/schemas/analysis.py
backend/app/api/v1/endpoints/analysis.py
backend/app/core/config.py            # LLM_MAX_TOKENS=4000
backend/tests/test_stats.py
backend/tests/test_analysis_api.py
backend/tests/test_llm_service.py
```

---

## 3. 统计 facts（Python 计算，LLM 只解释）

`stats.compute_facts` 输出：

| 指标 | 本次任务值 |
|---|---|
| 目标总数 | 33 |
| 类别 | motor 17、car 11、pedestrian 2、people 2、truck 1 |
| 密度 | 15.91 个/百万像素，等级“中等” |
| 3×3 网格 | 上中 10、中心 10、左中 7、左下 4、下中 2 |
| 最近邻 | 均值 57.2 px、中位数 45.4 px、占对角线 2.6% |
| 边缘目标 | 0，比例 0.0% |
| 尺寸 | 小 24、中 9、大 0 |
| 置信度 | 均值 0.419，最低 0.2579，最高 0.8414；低置信（<0.4）20，高置信（≥0.7）5 |
| 重叠 | IoU>0.5 共 2 对（抽样 33 个） |

阈值定义：

- 密度：稀疏 <5，中等 5–20，密集 20–50，极密集 >50（目标/百万像素）
- 尺寸：小 <0.1%，中 0.1%–1%，大 >1%（面积占图像比例）
- 置信度：低 <0.4，高 ≥0.7

---

## 4. LLM 配置与客户端

`.env` 实测配置：

| 项 | 值 |
|---|---|
| `LLM_BASE_URL` | 阿里云 MaaS `.../compatible-mode/v1` |
| `LLM_MODEL` | `deepseek-v4-pro` |
| `LLM_TIMEOUT_SECONDS` | 120 |
| `LLM_MAX_TOKENS` | 4000 |
| `LLM_TEMPERATURE` | 0.2 |
| `LLM_MAX_RETRIES` | 2 |
| JSON mode | ✅ 已验证 |
| Embedding（P5） | `qwen3.7-text-embedding`，dim 1024（原 `text-embedding-3-small` 返回 404，已修正） |

`deepseek-v4-pro` 是推理模型，会消耗 reasoning tokens；`max_tokens=32` 时曾返回空内容。
P4 使用 4000 token 预算，真实报告 completion_tokens=1928。

`llm_service`：

- `AsyncOpenAI`，超时/重试来自配置；
- `response_format={"type":"json_object"}`，不支持时降级为普通 JSON 提示；
- 提取 Markdown fence 内的 JSON；
- 空内容、截断、非法 JSON 映射为 `LLM_OUTPUT_INVALID`；
- 超时/鉴权/限流/上游错误分别映射为 504/502/503/502；
- 日志只记录模型、耗时、token，不记录 Key。

---

## 5. Prompt 与防幻觉

System Prompt 明确：

1. 只能使用 facts 的数字/类别/统计，不得修改或补全数量；
2. 不得编造 mAP、precision、recall、训练集、硬件性能；
3. 密度/网格/最近邻/边缘/尺寸均为检测框启发式统计；
4. 只输出 8 个键的 JSON；
5. 每个字段必须是字符串；
6. 阈值/定义/计数是最终值，characteristics 必须使用 facts 中的 0.4/0.7 阈值。

JSON 校验：

- `AnalysisSections` 8 个必填字段，每个 `min_length=1`；
- 非字符串值（对象/数组/数字）会转成可读字符串；
- 缺字段/空字段重试 1 次，仍失败返回 502，不写半成品报告。

Mock：

- `LLM_MOCK=true` 时由 Python 生成确定性 8 段文本；
- `is_mock=true`、`model_name=llm-mock`；
- limitations 明确写“Mock 模式，未调用 LLM，不能作为真实结论”。

---

## 6. API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/analysis/{task_id}` | 生成报告；`{"force": true}` 重新生成 |
| GET | `/api/v1/analysis/{task_id}` | 最新报告 |

错误：

| HTTP | code | 场景 |
|---|---|---|
| 404 | `TASK_NOT_FOUND` | 任务不存在 |
| 404 | `ANALYSIS_NOT_FOUND` | 还没有报告 |
| 409 | `TASK_NOT_READY` | 任务不是 success |
| 502 | `LLM_OUTPUT_INVALID` | 空内容/截断/非法 JSON/缺字段 |
| 503 | `LLM_NOT_CONFIGURED` | 无 Key/Model |
| 504 | `LLM_TIMEOUT` | 超时 |

---

## 7. 真实验收

检测任务：`d8165b1878d3410a835be9a53150d07f`
图像：`visdrone-sample.jpg`（1920×1080，33 个目标）

```text
report_id       = 2
model_name      = deepseek-v4-pro
is_mock         = false
latency_ms      = 34924
prompt_tokens   = 2604
completion_tokens = 1928
content_length  = 999
```

8 个字段全部生成，示例：

```text
overall_count: 共检测到 33 个目标。
class_distribution: motor 17 个（51.52%），car 11 个（33.33%），
  pedestrian 2 个（6.06%），people 2 个（6.06%），truck 1 个（3.03%）。
density_analysis: 每百万像素目标数 15.91，密度等级为“中等”...
characteristics: 置信度均值 0.419，最低 0.2579，最高 0.8414；
  低置信度（<0.4）目标 20 个，高置信度（≥0.7）目标 5 个...
limitations: 未提供 ground truth、mAP、precision、recall，无法评估真实精度...
```

`GET /api/v1/analysis/{task_id}` 返回同一份 `report_id=2`。

### 过程中的一次修正

第一次真实报告（report_id=1）文字把置信度阈值写成了 `<0.5 / ≥0.5`（计数仍是 20/5）。
这是 LLM 改写阈值，不是 facts 错误。修复方式：

- facts 中显式加入 `low_confidence_threshold=0.4`、`high_confidence_threshold=0.7`；
- Prompt 明确“不得改写成 0.5”；
- `force=true` 重新生成 report_id=2，文字变为 `<0.4 / ≥0.7`；
- 删除错误的 report_id=1，仅保留正确的 report_id=2。

---

## 8. 测试

```text
pytest:    33 passed in 12.14s
ruff:      All checks passed!
pip check: No broken requirements found.
```

新增覆盖：

- facts：角落网格、密度、最近邻、边缘、尺寸、置信度、重叠、空结果；
- JSON 提取：plain / fenced / leading text / invalid；
- Analysis API：Mock 报告 8 段、GET 最新、force 重新生成、pending 任务 409、缺任务 404、缺报告 404。

测试环境显式设置 `LLM_MOCK=true` 且清空 Key/Model，不会调用真实 LLM。

---

## 9. 验收清单

- [x] Python 计算 facts，LLM 只拿 facts
- [x] 8 段固定结构 + Markdown 标题由 Python 拼接
- [x] JSON mode + Pydantic 校验 + 1 次修复
- [x] 数量/类别/密度/网格/置信度与 facts 一致
- [x] 不编造 mAP/ground truth，limitations 明确说明
- [x] `LLM_MOCK` 明确标识 `is_mock=true`
- [x] 报告 Markdown + 结构化 JSON + token/耗时落库
- [x] GET/force/409/404 错误语义
- [x] 真实 `deepseek-v4-pro` 报告生成成功
- [x] 33 个测试通过，ruff 通过
- [x] 保留 1 个真实任务 + 1 份正确报告供后续前端联调

数据库当前保留：

```text
task:   d8165b1878d3410a835be9a53150d07f（33 个目标）
report: id=2（is_mock=false，deepseek-v4-pro）
```

---

## 10. 下一阶段（P5）

P5 将实现 RAG：

1. PDF/DOCX/TXT 解析（保留页码/段落）；
2. 清洗、切分、Embedding（`qwen3.7-text-embedding`，1024 维）；
3. FAISS 索引（`IndexFlatIP` + 归一化）；
4. 检索 + 阈值 + 引用（文档名/页码/片段/相似度）；
5. `knowledge/upload`、`documents`、`delete`、`search`；
6. 无检索结果时明确说明“知识库缺少依据”，不调用 LLM 编造。

Embedding 配置已验证，P5 不需要额外 Key。需要你提供 1–3 份测试文档（PDF/DOCX/TXT 均可），或我先用项目自身文档做验收。
