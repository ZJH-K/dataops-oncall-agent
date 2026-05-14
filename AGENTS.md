# AGENTS.md - DataOps OnCall Agent

## 1. 项目身份

项目名称：DataOps OnCall Agent

项目目标：构建一个面向求职面试的 AI Agent 应用，用于 DataOps 数据故障诊断。

这个项目服务于快速求职。优先级不是做一个生产级数据平台，而是做出一个可以本地运行、可以解释、可以测试、可以演示的 MVP，用来支撑 AI 应用开发 / Agent 应用开发 / Python 后端相关岗位的简历和面试。

## 2. 当前项目进度

当前阶段：B9 README 和面试材料已完成，MVP 项目闭环完成。

已完成：

```text
[x] docs/01-product-requirements.md
[x] docs/02-user-stories.md
[x] docs/03-user-flow.md
[x] docs/04-technical-design.md
[x] docs/05-api-spec.md
[x] docs/06-database-schema.md
[x] docs/07-test-cases.md
[x] docs/08-deployment.md
[x] docs/09-challenges-and-solutions.md
[x] docs/10-interview-talking-points.md
[x] AGENTS.md
[x] TASKS.md
[x] B0 项目脚手架
[x] B1 SQLite schema + seed 数据
[x] B2 Diagnosis Skill Center
[x] B3 MCP Tool server
[x] B4 RAG 知识检索
[x] B5 LangGraph 诊断工作流
[x] B6 FastAPI 接口
[x] B7 Demo UI
[x] B8 测试和 eval
[x] B9 README 和面试材料
```

未开始：

```text
无
```

当前下一步：

```text
项目 MVP 已完成。已接入 DeepSeek 决策辅助和阿里云 text-embedding-v4 hybrid RAG，并已明确当前版本是 single-agent workflow，不是 Multi-Agent。下一步可以做 Demo UI 展示 LLM 决策节点、截图/GIF 增强、真实系统 provider 设计，或继续扩展更多测试数据。
```

当某个批次完成后，需要同步更新本节和 `TASKS.md` 中对应批次状态。

## 3. 上下文读取策略

不要一上来读取 docs 目录下所有文档。这样会浪费上下文，也会让实现过程失焦。

每次新对话的默认读取顺序：

```text
1. AGENTS.md
2. TASKS.md
3. 当前批次对应的主文档
4. 当前批次需要时再读取辅助文档
```

`docs/04-technical-design.md` 是技术实现主文档。做大多数开发批次时，优先读它；其他文档只在涉及到对应内容时再读。

如果上下文很紧，只读：

```text
AGENTS.md
TASKS.md
docs/04-technical-design.md 的相关章节
```

## 4. 分批次文档阅读规则

| 批次 | 当前任务 | 必读文档 | 按需参考 |
|------|----------|----------|----------|
| B0 | 项目脚手架 | `docs/04-technical-design.md` 的目录结构和技术栈章节 | `docs/08-deployment.md` |
| B1 | SQLite schema + seed 数据 | `docs/06-database-schema.md` | `docs/07-test-cases.md`、`docs/04-technical-design.md` |
| B2 | Diagnosis Skill Center | `docs/04-technical-design.md` 的 Diagnosis Skill 章节 | `docs/01-product-requirements.md`、`docs/02-user-stories.md` |
| B3 | MCP Tool server | `docs/04-technical-design.md` 的 MCP Tool 章节 | `docs/06-database-schema.md`、`docs/05-api-spec.md` |
| B4 | RAG 知识检索 | `docs/04-technical-design.md` 的 RAG 章节 | `docs/09-challenges-and-solutions.md` |
| B5 | LangGraph 诊断工作流 | `docs/04-technical-design.md` 的 LangGraph Workflow 章节 | `docs/03-user-flow.md`、`docs/09-challenges-and-solutions.md` |
| B6 | FastAPI 接口 | `docs/05-api-spec.md` | `docs/04-technical-design.md` |
| B7 | Demo UI | `docs/03-user-flow.md` 的页面流程和演示流程 | `docs/05-api-spec.md`、`docs/10-interview-talking-points.md` |
| B8 | 测试和 eval | `docs/07-test-cases.md` | `docs/09-challenges-and-solutions.md` |
| B9 | README 和面试材料 | `docs/10-interview-talking-points.md` | `docs/08-deployment.md`、`docs/09-challenges-and-solutions.md` |

除非用户明确要求，否则不要在一个批次里批量读取 10 个 docs 文档。

## 5. 项目核心定位

这个项目不是通用聊天机器人，也不是网上售卖 Agent 项目的改名版。

它是一个 DataOps OnCall 诊断工作流：

```text
用户告警
  -> AlertParser
  -> DiagnosisSkillMatcher
  -> RAG KnowledgeRetriever
  -> Planner
  -> MCP ToolExecutor
  -> CoverageChecker
  -> Reporter
  -> IncidentRecorder
```

必须始终保持以下边界清晰：

```text
Diagnosis Skill = 诊断策略和证据要求
RAG = Runbook、表说明、质量规则、历史事故复盘
MCP Tool = 具体查询或写入动作
LangGraph = 工作流编排和状态流转
SQLite = 可复现的模拟数据平台
CoverageChecker = 防止证据不足时过早下结论
Session State = 支持多轮追问和上下文延续
```

## 6. 术语规则

正式术语使用 `Diagnosis Skill`，不要在代码或文档中强行翻译成“技能”。

正确解释：

```text
Diagnosis Skill 是面向某一类 DataOps 故障的可配置诊断策略，类似 Runbook Playbook。它定义触发条件、必需工具、证据要求、风险等级和输出格式。
```

不要把 Diagnosis Skill 描述成：

```text
- 工具
- 只有 Prompt
- Codex skill
- MCP Tool
```

## 7. MVP 范围

先只做这 4 个场景：

```text
1. airflow_task_failed
2. partition_missing
3. data_volume_drop
4. null_rate_spike
```

最推荐的演示场景是 `data_volume_drop`：

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

这个场景应该能展示：

```text
Diagnosis Skill 匹配
RAG Runbook 检索
MCP Tool 调用
CoverageChecker
最终事故报告
Session State 多轮追问
```

## 8. 实现原则

优先做一个小而可运行的 MVP，不要一开始追求大而全。

第一版优先使用轻量本地组件：

```text
FastAPI
LangGraph
SQLite
本地 MCP Server
轻量 RAG index
简单前端或静态 UI
pytest
```

第一版避免依赖这些重组件：

```text
真实 Airflow
真实 Hive
真实 Spark/Flink
真实 DataHub
Milvus
Kubernetes
复杂权限系统
多租户系统
```

解释项目时要诚实：

```text
当前版本使用 SQLite 模拟数据平台元数据和故障场景。工作流设计成 provider 可替换，后续可以接入 Airflow API、Hive Metastore、DataHub 或数据质量平台。
```

不要声称已经接入真实生产系统，除非真的实现了。

## 9. 工程约束

- 项目必须能本地运行。
- 每个批次只做当前任务，不要顺手扩展后续大模块。
- 每个批次结束时都要给出可执行的验证命令。
- 模块行为稳定后尽快补测试。
- 4 个 MVP 场景跑通前，不要扩展更多场景。
- 不要吞掉工具失败。工具失败必须出现在日志和最终报告里。
- 最终报告必须引用工具证据或 RAG 来源。
- 如果证据不足，报告必须明确说明，不要输出过度确定的根因。

## 10. 推荐技术栈

第一版推荐：

```text
Python 3.11+
FastAPI
Pydantic
LangGraph
FastMCP 或 MCP Python SDK
SQLite
Chroma / FAISS / SQLite FTS 作为轻量 RAG
pytest
简单 HTML/JS 前端或 Streamlit
```

如果某个库的安装或集成变成阻塞，优先选择更简单的方案，但要保持架构可解释。

## 11. 新对话启动提示词

在项目区新开 AI 对话时，使用这段提示词：

```text
你现在在 DataOps OnCall Agent 项目中。请先阅读 AGENTS.md 和 TASKS.md。当前任务是 B0 - 项目脚手架。请只做 B0：项目基础结构、pyproject.toml、.env.example、/api/health 和 README 占位。不要实现完整 Agent。需要参考文档时，优先看 docs/04-technical-design.md 的目录结构和技术栈章节，必要时再看 docs/08-deployment.md。完成后运行验证命令，并更新 AGENTS.md 当前项目进度和 TASKS.md 的 B0 状态。
```

后续批次的新对话提示词格式：

```text
请先阅读 AGENTS.md 和 TASKS.md。当前任务是 Bx - [批次名]。请根据 AGENTS.md 的分批次文档阅读规则，只阅读当前批次必需文档，不要一次性读取全部 docs。完成后运行验证命令，并更新 AGENTS.md 当前项目进度和 TASKS.md 状态。
```

如果任务是面试准备，再读取：

```text
docs/09-challenges-and-solutions.md
docs/10-interview-talking-points.md
```

## 12. 当前简历可投安全线

项目达到以下条件后，才适合写进简历主项目：

```text
- 能本地运行。
- SQLite demo 数据可以 reset 和 seed。
- 至少 2 个 MVP 场景能端到端跑通。
- data_volume_drop 场景可以稳定演示。
- Diagnosis Skill 匹配过程可见。
- MCP Tool 调用有日志。
- 报告里能看到 RAG 引用来源。
- CoverageChecker 结果可见。
- Session State 支持至少一个多轮追问。
- README 说明安装、演示、架构和限制。
- 你能用 2 分钟讲清楚项目。
```

## 13. 面试诚实边界

推荐说法：

```text
我实现了一个可运行原型，用 SQLite 模拟 DataOps 元数据，用来验证 Agent 诊断工作流。
```

避免说法：

```text
我接入了真实生产 Airflow 和数仓系统。
```

推荐说法：

```text
Diagnosis Skill 定义诊断策略，MCP Tool 执行具体查询。
```

避免说法：

```text
Skill 就是工具。
```
