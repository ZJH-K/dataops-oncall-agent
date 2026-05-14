# 02 User Stories - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：01-product-requirements.md

## 1. 文档目标

本文档用于定义 DataOps OnCall Agent 的核心用户故事。项目目标不是覆盖所有数据平台场景，而是围绕求职面试可讲清楚、可演示、可追问的 MVP 范围，设计 4 类典型 DataOps 故障诊断故事。

每个用户故事都需要体现以下能力：

- 告警理解：系统能从自然语言中提取表名、任务名、时间范围和异常类型。
- Diagnosis Skill 匹配：系统能选择合适的诊断策略。
- RAG 检索：系统能检索 Runbook、表说明或历史事故复盘。
- MCP Tool 调用：系统能查询模拟数据平台中的任务、分区、数据量、质量检查和血缘。
- 证据覆盖：系统能检查关键工具和证据是否齐全。
- 报告生成：系统能输出可追溯的事故诊断报告。

## 2. 用户画像

### 2.1 数据开发工程师

负责开发和维护离线数据任务、指标加工 SQL、日报宽表和数据质量规则。收到告警后，需要快速判断问题发生在哪个任务、哪张表、哪个上游依赖。

典型关注点：

- 哪个任务失败了？
- 哪张表没产出？
- 是当前任务问题，还是上游数据没到？
- 下游报表会不会受影响？

### 2.2 数据平台值班人员

负责早晚高峰或夜间值班，处理调度失败、质量异常、报表延迟等问题。希望系统能减少手动查询多个平台的时间。

典型关注点：

- 告警属于哪类问题？
- 按什么步骤排查？
- 需要查哪些系统？
- 报告能不能快速发给业务方？

### 2.3 数据质量负责人

关注数据质量规则和异常影响范围。希望系统能说明异常指标、异常幅度、影响表和后续修复建议。

典型关注点：

- 异常是否真实？
- 异常影响多大？
- 是否影响下游核心指标？
- 是否需要升级为数据事故？

### 2.4 面试官视角

面试官不是系统真实用户，但本项目需要支持面试官追问。项目需要让面试官看到：候选人不是只做了一个聊天 Demo，而是设计了一个有业务约束、状态管理、工具调用、证据校验和评估意识的 Agent 应用。

面试官可能追问：

- Diagnosis Skill 和 MCP Tool 的区别是什么？
- 为什么不用一个大 Prompt 解决所有故障？
- RAG 检索错 Runbook 怎么办？
- 工具调用漏了怎么发现？
- 模拟数据如何迁移到真实 Airflow 或 Hive 环境？

## 3. 用户故事总览

| ID | 用户故事 | 主要 Diagnosis Skill | 优先级 | MVP |
|----|----------|----------------------|--------|-----|
| US-001 | 诊断 Airflow 任务失败 | `airflow_task_failed` | P0 | 是 |
| US-002 | 诊断表分区缺失 | `partition_missing` | P0 | 是 |
| US-003 | 诊断数据量突降 | `data_volume_drop` | P0 | 是 |
| US-004 | 诊断字段空值率异常 | `null_rate_spike` | P0 | 是 |
| US-005 | 追问影响范围 | 复用上一个 Diagnosis Skill | P1 | 是 |
| US-006 | 生成事故报告 | `incident_report` workflow | P1 | 是 |
| US-007 | 低置信度时请求澄清 | `skill_disambiguation` | P1 | 是 |
| US-008 | 查看历史诊断记录 | 无固定 Skill | P2 | 否 |
| US-009 | 新增 Diagnosis Skill | Diagnosis Skill Center | P2 | 否 |

## 4. P0 用户故事

### US-001：诊断 Airflow 任务失败

作为数据开发工程师，
我希望在收到 Airflow 任务失败告警后，系统能自动识别失败任务，查询任务运行状态、失败原因、关联表和下游影响，
以便我快速判断是否需要重跑任务或通知下游业务方。

示例输入：

```text
DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。
```

期望系统行为：

1. AlertParser 提取 `dwd_order_detail_daily`、今天、任务失败。
2. DiagnosisSkillMatcher 匹配 `airflow_task_failed`。
3. RAG 检索 Airflow 任务失败 Runbook。
4. MCP Tool 调用 `query_task_runs` 查询任务状态。
5. MCP Tool 调用 `query_lineage` 查询该任务产出表和下游影响。
6. CoverageChecker 检查 `airflow_task_failed` 必需工具是否调用完整。
7. Reporter 输出包含失败任务、失败时间、失败原因、影响范围和建议动作的报告。

验收标准：

- 系统能匹配 `airflow_task_failed`。
- 报告中包含任务名、运行时间、失败状态和错误摘要。
- 报告中说明影响了哪些下游表或报表。
- 如果工具返回失败，报告必须说明证据不足。

关键数据依赖：

- `dags`
- `task_runs`
- `data_tables`
- `lineage_edges`
- `tool_call_logs`

面试讲解点：

> 这个故事体现了 Agent 不是直接生成答案，而是先匹配 Diagnosis Skill，再按照 Diagnosis Skill 的证据要求调用工具。任务失败不是只查任务状态，还要查下游血缘，避免只回答表面错误。

### US-002：诊断表分区缺失

作为数据平台值班人员，
我希望在发现某张表今日分区未产出时，系统能检查当前表、上游表和相关任务，
以便判断是当前任务失败、上游数据缺失，还是调度依赖未完成。

示例输入：

```text
dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。
```

期望系统行为：

1. AlertParser 提取 `dws_sales_daily`、`dt=2026-05-14`、分区缺失。
2. DiagnosisSkillMatcher 匹配 `partition_missing`。
3. RAG 检索分区缺失 Runbook 和表说明。
4. MCP Tool 调用 `query_table_partitions` 查询当前表分区。
5. MCP Tool 调用 `query_lineage` 查询上游依赖表。
6. MCP Tool 调用 `query_task_runs` 查询当前表和上游表相关任务。
7. Reporter 判断问题位于当前任务、上游表还是调度链路。

验收标准：

- 系统能识别表名和分区日期。
- 报告不能只说“分区不存在”，必须进一步检查上游和任务状态。
- 报告能区分当前表未产出和上游表未就绪。
- 报告包含建议动作，例如等待上游、重跑任务、联系上游负责人。

关键数据依赖：

- `data_tables`
- `table_partitions`
- `task_runs`
- `lineage_edges`

面试讲解点：

> 分区缺失是 DataOps 中最容易讲清楚的场景。它能自然引出血缘分析：一张下游表没产出，不一定是自身任务失败，也可能是上游表缺分区。

### US-003：诊断数据量突降

作为数据质量负责人，
我希望在发现某张核心表今日数据量较昨日大幅下降时，系统能自动查询历史行数、任务状态、分区和血缘影响，
以便判断是否构成数据事故。

示例输入：

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

期望系统行为：

1. AlertParser 提取 `dws_sales_daily`、今日、下降 92%、数据量突降。
2. DiagnosisSkillMatcher 匹配 `data_volume_drop`。
3. RAG 检索数据量异常 Runbook、表口径说明和历史事故复盘。
4. MCP Tool 调用 `query_data_volume` 查询最近 7 天行数趋势。
5. MCP Tool 调用 `query_task_runs` 查询相关任务状态。
6. MCP Tool 调用 `query_table_partitions` 查询当前表和关键上游表分区。
7. MCP Tool 调用 `query_lineage` 查询下游影响范围。
8. CoverageChecker 检查行数趋势、任务状态、分区和血缘证据是否齐全。
9. Reporter 输出根因判断和影响范围。

验收标准：

- 报告包含最近 7 天数据量趋势。
- 报告包含下降比例。
- 报告说明是否影响下游 ADS 报表或业务看板。
- 如果没有查任务状态或分区，CoverageChecker 应提示证据不足。

关键数据依赖：

- `table_partitions`
- `data_volume_stats`
- `task_runs`
- `lineage_edges`
- `postmortems`

面试讲解点：

> 这个故事最适合展示项目深度，因为数据量突降不能只看行数。需要结合任务、分区、上游依赖和历史事故，最后还要避免证据不足时过度下结论。

### US-004：诊断字段空值率异常

作为数据开发工程师，
我希望在某个字段空值率突然升高时，系统能定位异常字段、查询质量检查结果、查看上游来源和下游影响，
以便判断是否需要修复数据或通知使用方。

示例输入：

```text
ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。
```

期望系统行为：

1. AlertParser 提取 `ads_user_profile`、`user_id`、空值率异常。
2. DiagnosisSkillMatcher 匹配 `null_rate_spike`。
3. RAG 检索字段质量异常 Runbook 和表字段说明。
4. MCP Tool 调用 `query_null_rate` 查询字段历史空值率。
5. MCP Tool 调用 `query_lineage` 查询上游来源和下游使用方。
6. MCP Tool 调用 `query_task_runs` 查询相关任务是否异常。
7. Reporter 输出异常字段、异常幅度、可能根因和影响范围。

验收标准：

- 系统能识别表名和字段名。
- 报告包含历史空值率对比。
- 报告说明异常字段影响哪些下游表或报表。
- 如果字段名缺失，系统需要追问用户补充字段，而不是编造。

关键数据依赖：

- `quality_checks`
- `data_tables`
- `lineage_edges`
- `task_runs`

面试讲解点：

> 字段空值率异常能体现数据质量思维。这个故事可以讲清楚为什么 Agent 需要结构化状态，因为用户后续追问“它影响哪些报表”时，系统需要知道“它”指的是哪个表和字段。

## 5. P1 用户故事

### US-005：多轮追问影响范围

作为值班人员，
我希望在系统完成一次诊断后，可以继续追问影响范围、证据来源或处理建议，
以便不用重复输入表名、任务名和事故上下文。

示例对话：

```text
用户：dws_sales_daily 今日数据量下降 92%，帮我诊断。
系统：已匹配 data_volume_drop，并生成诊断报告。
用户：它影响哪些下游报表？
系统：根据当前 incident 的 lineage 查询结果，影响 ads_sales_report 和 ads_revenue_dashboard。
```

验收标准：

- 系统保存 `session_id`、`incident_id`、`selected_diagnosis_skill`、`alert_context` 和 `evidence`。
- 用户使用“它”“这个表”“这个任务”时，系统能结合结构化状态回答。
- 系统不能只依赖聊天历史，需要使用结构化 Session State。

面试讲解点：

> 多轮记忆不是简单把所有聊天塞进上下文，而是把当前事故对象、已查证据和诊断状态结构化保存。

### US-006：生成事故报告

作为数据质量负责人，
我希望系统在诊断结束后生成一份 Markdown 事故报告，
以便同步给业务方、记录在事故库中，并作为后续 RAG 的历史案例。

报告字段：

- 告警摘要。
- Diagnosis Skill。
- 诊断步骤。
- 工具调用证据。
- 根因判断。
- 影响范围。
- 修复建议。
- 风险等级。
- 引用来源。
- 证据不足说明。

验收标准：

- 报告保存到 `incidents` 或 `incident_reports`。
- 报告包含工具调用证据和 RAG 引用。
- 缺少关键证据时，报告明确说明“不足以确认根因”。

面试讲解点：

> 事故报告让项目从聊天 Demo 变成业务闭环。诊断结果可以沉淀成历史案例，后续还能进入 RAG 知识库。

### US-007：低置信度时请求澄清

作为用户，
我希望当告警描述不清楚时，系统不要强行选择错误的 Diagnosis Skill，
而是给出候选问题类型并让我补充信息。

示例输入：

```text
今天销售报表不太对，帮我看看。
```

期望系统行为：

- 返回候选 Diagnosis Skill：`partition_missing`、`data_volume_drop`、`null_rate_spike`。
- 说明缺少的信息：表名、指标名、异常类型、时间范围。
- 向用户提出澄清问题。

验收标准：

- 低置信度时不强行生成根因报告。
- 返回候选 Diagnosis Skill 和匹配理由。
- 澄清后能继续同一 session 的诊断流程。

面试讲解点：

> 这个故事用来回答“模型高置信度但路由错误怎么办”。我的处理是候选召回、置信度阈值和澄清机制。

## 6. P2 扩展用户故事

### US-008：查看历史诊断记录

作为值班人员，
我希望能查看历史事故和诊断报告，
以便对比相似案例。

MVP 不强制实现完整页面，但数据库设计需要预留 `incidents`、`incident_reports` 和 `tool_call_logs`。

### US-009：新增 Diagnosis Skill

作为项目维护者，
我希望通过新增一个目录来扩展新的 Diagnosis Skill，
以便后续支持 SQL 执行失败、指标环比异常或 Flink 延迟等场景。

期望目录：

```text
skills/
└── sql_execution_failed/
    ├── skill.yaml
    ├── runbook.md
    └── examples.json
```

验收标准：

- 新增目录后，系统能自动加载 Skill metadata。
- Diagnosis Skill matcher 能把新 Skill 纳入候选集合。
- 不需要改核心 Agent 工作流。

## 7. 反例与边界

### 7.1 不应该发生的行为

- 用户只说“数据有问题”，系统直接编造具体表名。
- 没有调用必需工具，系统却给出确定根因。
- RAG 没有召回相关文档，系统却声称“根据 Runbook”。
- MCP Tool 查询失败，报告中不说明失败。
- 把 Diagnosis Skill 当成具体工具调用。

### 7.2 系统应该如何降级

- 缺少表名：请求用户补充表名。
- Skill 匹配低置信度：返回候选 Skill 并澄清。
- RAG 结果不足：说明缺少知识依据。
- MCP Tool 失败：保留失败日志并在报告中说明。
- 证据覆盖不足：输出初步判断，不输出确定根因。

## 8. 面试讲解主线

本项目的用户故事可以组织成一条面试主线：

```text
我选择了 DataOps OnCall 场景，因为它和我的数据专业背景相关，也天然适合 Agent 的工具调用和诊断流程。项目不是做通用问答，而是围绕 4 类典型数据故障设计 Diagnosis Skill。每个 Skill 定义触发条件、必需工具和证据要求。Agent 接到告警后先匹配 Skill，再检索 Runbook，调用 MCP Tool 查询模拟数据平台，最后通过 Coverage Checker 防止工具没查全就下结论。
```

最推荐演示的故事顺序：

1. US-003 数据量突降：展示完整诊断深度。
2. US-005 多轮追问：展示结构化 Session State。
3. US-007 低置信度澄清：展示对模型错误路由的处理。
4. US-006 事故报告：展示业务闭环。

