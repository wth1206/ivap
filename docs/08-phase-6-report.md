# 第六阶段实施报告（P6）

> 阶段：P6 LangGraph Agent
> 日期：2026-11-06
> 结论：**通过**（真实 LLM 工具调用、5 个工具、会话持久化、引用与工具轨迹；45 个测试通过）
> 设计：[01-architecture-design.md](01-architecture-design.md) §5.6
> 前置：[07-phase-5-report.md](07-phase-5-report.md)

---

## 1. 本阶段目标

1. LangGraph `StateGraph` 主 Agent；
2. 5 个工具：检测、任务详情、统计、RAG 检索、分析报告；
3. 自然语言路由、工具循环、最大步数、超时；
4. 工具失败如实返回，不伪造结果；
5. 会话/消息/工具轨迹/引用持久化；
6. `POST /chat`、`GET /chat/history`；
7. 真实 LLM 工具编排验收。

---

## 2. 交付文件

```text
backend/app/agents/
├── state.py          # AgentState
├── prompts.py        # 系统提示 + 当前任务/图片上下文
├── tools.py          # 5 个工具、Pydantic 参数、ToolContext
├── graph.py          # prepare → agent ⇄ tools → finalize
└── runner.py         # 超时、结果归一化

backend/app/services/chat_service.py
backend/app/schemas/chat.py
backend/app/api/v1/endpoints/chat.py
backend/tests/test_chat_api.py
backend/tests/test_agent_tools.py
```

`LLMService.chat_with_tools` 新增 OpenAI 工具调用支持。

---

## 3. LangGraph 工作流

```text
START
 → prepare（系统提示 + 当前 task_id/image_path + 历史消息）
 → agent（LLM + tools schema）
 → 有 tool_calls 且 step < max_steps → tools（执行、记录轨迹/引用/耗时）
 → 回到 agent
 → 无 tool_calls → finalize → END
```

- `AGENT_MAX_STEPS` 默认 6；
- `AGENT_TIMEOUT_SECONDS` 默认 180；
- 单个工具输出截断到 12,000 字符；
- 工具异常转为带 `error.code/message` 的工具消息，Agent 必须如实转述；
- 工具调用记录：`name / arguments / status / duration_ms / error_code`；
- `requires_confirmation` 字段已保留；当前 5 个工具均为检测/查询/报告，不含删除或改配置类操作。

---

## 4. 五个工具

| 工具 | 参数 | 说明 |
|---|---|---|
| `detect_image` | `image_path?`, `model_name?`, `conf?`, `iou?` | 调用 ECE-YOLO 检测；省略路径时用当前会话图片 |
| `get_detection_result` | `task_id?`, `include_detections`, `limit` | 查询任务状态、类别统计、目标框 |
| `get_detection_statistics` | `task_id?`, `start_time?`, `end_time?` | 单任务或历史聚合统计 |
| `search_knowledge_base` | `query`, `top_k?` | RAG 检索，返回页码/片段/分数 |
| `generate_analysis_report` | `task_id?` | 生成或复用 8 段分析报告 |

`task_id` 支持从当前会话上下文补全；`detect_image` 成功后会把新任务写入上下文，供后续报告工具使用。

---

## 5. API

### POST /api/v1/chat

```json
{
  "message": "查询任务 d816... 的统计信息",
  "conversation_id": null,
  "task_id": "d816...",
  "image_path": null
}
```

响应：

```json
{
  "conversation_id": "...",
  "message_id": 1,
  "answer": "...",
  "citations": [],
  "tool_calls": [
    {"name": "get_detection_statistics", "arguments": {"task_id": "..."}, "status": "success", "duration_ms": 7, "error_code": null}
  ],
  "requires_confirmation": false,
  "usage": {"prompt_tokens": 0, "completion_tokens": 0},
  "is_mock": false,
  "created_at": "...Z"
}
```

### GET /api/v1/chat/history

- 不带 `conversation_id`：会话列表（标题、最后消息、更新时间）；
- 带 `conversation_id`：该会话消息，含 assistant 的 `tool_calls` 与 `citations`。

---

## 6. 真实验收（deepseek-v4-pro）

### 6.1 任务统计

```text
用户：查询任务 d8165b... 的统计信息
工具：get_detection_statistics / success / 7ms
回答：33 个目标；motor 17、car 11、people 2、pedestrian 2、truck 1
```

### 6.2 知识库问答

```text
用户：VisDrone 数据集包含哪些目标类别？
工具：search_knowledge_base / success / 659ms
引用：4 条
回答：10 个类别，引用 [S1][S2][S3]
```

引用包含：

```text
[S1] visdrone_overview.pdf p.1  0.8323
[S2] visdrone.txt               0.7049
[S3] ece_yolo.docx              0.6802
[S4] visdrone_overview.pdf p.2  0.5174
```

### 6.3 分析报告

```text
用户：请为任务 d8165b... 生成分析报告
工具：generate_analysis_report / success / 5ms
结果：复用已有 report_id=2，返回完整 8 段报告
```

### 6.4 任务详情

```text
用户：查询任务 d8165b... 的检测结果，列出前 5 个目标
工具：get_detection_result / success / 5ms
回答：33 个目标；前 5 个均为 car，含置信度与 bbox
```

### 6.5 图片检测

```text
用户：请对这张图片重新执行目标检测...
上下文：image_path=images/2026/11/...jpg
工具：detect_image / success / 519ms
新任务：fb1bdfc5211d477fba55562c8c0d4cd9（33 个目标）
```

验收后已删除该临时任务，保留原 P4 任务与报告。

---

## 7. 会话持久化

- 每次 `POST /chat` 写入 user/assistant 两条 `chat_messages`；
- assistant 消息保存 `tool_calls`、`citations`、`token_usage`；
- 会话标题取首条消息前 60 字；
- `GET /chat/history` 已验证返回工具轨迹和引用；
- 测试中 `LLM_MOCK=true` 时返回明确 Mock 回答，不调用真实 LLM。

---

## 8. 测试

```text
pytest:    45 passed in 13.68s
ruff:      All checks passed!
pip check: No broken requirements found.
```

新增覆盖：

- `POST /chat` Mock 回答、会话创建、历史消息、二次对话；
- 未知会话 404、空消息 422；
- 5 个工具直接调用：
  - 任务详情 / 统计；
  - RAG 检索 + 引用提取；
  - detect_image（Mock 模型）；
  - generate_analysis_report（Mock LLM）；
  - 工具错误返回 `TASK_NOT_FOUND` 而不是抛 500。

---

## 9. 验收清单

- [x] LangGraph StateGraph 工作流
- [x] 5 个工具全部可调用
- [x] 真实 `deepseek-v4-pro` function calling
- [x] 工具循环、最大步数 6、超时 180s
- [x] 工具失败显式返回错误码，不伪造
- [x] 检测 → 新任务写入上下文
- [x] RAG 引用保留 [S1] 编号
- [x] 会话/消息/工具轨迹/引用落库
- [x] `POST /chat`、`GET /chat/history`
- [x] `LLM_MOCK` 明确标识
- [x] 45 个测试通过，ruff 通过
- [x] 真实工具编排验收通过

---

## 10. 下一阶段（P7）

P7 将实现 Vue 3 前端 6 个页面：

1. 首页：统计卡片、类别分布、最近任务；
2. 图像检测：上传、参数、检测结果图、类别图表；
3. 智能分析：任务选择、8 段报告 Markdown；
4. 知识库：上传、文档列表、检索、引用；
5. Agent 对话：消息、工具轨迹、引用、会话历史；
6. 历史任务：筛选、分页、详情、删除。

后端 API 已全部就绪；P7 不需要新增 Key。Node/npm 已确认可用（本机用 `npm.cmd`）。
