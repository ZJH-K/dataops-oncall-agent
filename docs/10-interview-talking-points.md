# 10 Interview Talking Points - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：01-product-requirements.md、04-technical-design.md、09-challenges-and-solutions.md

## 1. 文档目标

本文档用于准备 DataOps OnCall Agent 的面试讲解。目标不是背稿，而是形成一套能根据面试官追问灵活展开的表达框架。

你要让面试官感受到：

- 你不是拿网上模板项目改名字。
- 你知道这个项目解决什么业务问题。
- 你能讲清楚 RAG、MCP、Diagnosis Skill、LangGraph 的边界。
- 你遇到或预判了 Agent 项目里的真实问题，并设计了解法。
- 你知道模拟数据和真实生产系统的差距，不乱吹。

## 2. 30 秒版本

```text
我做的是一个 DataOps OnCall Agent，面向数据平台故障诊断场景。当前版本不是 Multi-Agent，而是一个基于 LangGraph 的 single-agent workflow。它可以根据数据任务失败、表分区缺失、数据量突降、字段空值率异常等告警，匹配 Diagnosis Skill，检索 Runbook，调用 MCP Tool 查询任务、分区、数据量、质量检查和血缘信息，最后生成带证据链的事故报告。项目重点不是普通聊天，而是解决 Agent 在诊断场景中的路由错误、工具调用不完整、RAG 引用不可靠和多轮状态丢失问题。
```

## 3. 2 分钟版本

```text
这个项目叫 DataOps OnCall Agent，场景是数据平台值班。真实工作里，数据开发收到告警后通常要手动查调度任务、表分区、数据量、质量规则、血缘和历史事故文档。我把这个流程做成一个 Agent 应用。

系统接到自然语言告警后，先用 AlertParser 提取表名、任务名、字段、时间和异常类型；如果配置了 DeepSeek，它会参与上下文解析，但解析结果仍会被代码校验。然后 Diagnosis Skill Matcher 选择对应的诊断策略，例如 data_volume_drop 或 partition_missing；DeepSeek 可以辅助选择，但只能从内置 Skill 列表里选，不能创造新 Skill。每个 Diagnosis Skill 会定义触发条件、必需工具、证据要求和输出格式。接着系统用 RAG 检索 Runbook、表说明和历史事故；默认是关键词和 metadata 检索，如果配置阿里云百炼 text-embedding-v4，会启用 hybrid retrieval。然后 Planner 生成工具计划，MCP Tool 查询 SQLite 模拟的数据平台，包括 task_runs、table_partitions、data_volume_stats、quality_checks 和 lineage_edges。最后 CoverageChecker 会检查必需工具和证据是否齐全，避免工具没查全就下结论，再生成 Markdown 事故报告。

我重点处理了几个 Agent 项目常见问题：Skill 路由错误时通过候选 Skill 和置信度澄清；工具调用不完整时用 CoverageChecker；RAG 召回错误时用 metadata filter、embedding 和引用来源；多轮追问时不用纯聊天历史，而是用结构化 Session State 保存当前 incident、表、字段和证据。当前测试结果是 43 个 pytest 通过，Skill match、RAG hit rate 和 tool coverage 三个 eval 指标在固定数据集上都是 1.0。
```

## 4. 5 分钟版本结构

按这个顺序讲：

1. 背景：为什么选 DataOps OnCall。
2. 场景：支持 4 类故障。
3. 架构：FastAPI + LangGraph single-agent workflow + DeepSeek decision assistance + Diagnosis Skill + RAG + MCP Tool + SQLite。
4. 流程：输入告警到生成报告。
5. 深度：讲 2 个挑战和解决方案。
6. 边界：模拟数据如何迁移真实系统。
7. 结果：测试、eval、演示案例。

## 5. 项目背景怎么讲

### 5.1 推荐说法

```text
我本科是数据科学与大数据技术方向，所以我没有选择泛泛的客服 Agent，而是选了更贴近数据专业的 DataOps OnCall 场景。这个场景里的问题比较具体：任务失败、分区缺失、数据量异常、字段空值率异常。它天然需要查多个系统，也适合展示 Agent 的工具调用和状态管理能力。
```

### 5.2 不推荐说法

```text
因为 Agent 很火，所以我做了一个 Agent 项目。
```

这个说法太浅，容易被追问。

## 6. 业务场景怎么讲

### 6.1 四个 MVP 场景

```text
1. Airflow 任务失败：查任务状态、错误日志和下游影响。
2. 表分区缺失：查当前表分区、上游表分区和任务依赖。
3. 数据量突降：查 7 天行数趋势、任务状态、分区和血缘。
4. 字段空值率异常：查字段质量规则、历史空值率和下游影响。
```

### 6.2 人话解释

```text
这些场景本质上都在回答三个问题：数据为什么不对，影响了谁，接下来怎么处理。
```

## 7. 技术架构怎么讲

推荐表达：

```text
架构上我分成几层：FastAPI 提供接口和前端演示；LangGraph 编排 single-agent 诊断流程；DeepSeek 作为可选决策辅助参与告警解析、Skill 路由、规划和报告摘要；Diagnosis Skill Center 管理不同故障类型的诊断策略；RAG 检索 Runbook 和历史事故；MCP Tool 查询任务、分区、质量和血缘；SQLite 用来模拟数据平台元数据和演示故障场景。
```

如果面试官问为什么不用一个 Prompt：

```text
一个大 Prompt 很难约束工具调用和证据完整性。我把故障处理策略拆到 Diagnosis Skill，把流程拆到 LangGraph 节点，把工具调用交给 MCP Tool，再用 CoverageChecker 检查证据。这种结构更容易调试，也更容易扩展新故障类型。
```

## 8. Diagnosis Skill 怎么讲

### 8.1 一句话定义

```text
Diagnosis Skill 是某一类故障的可配置诊断策略，类似 Runbook Playbook。它不是工具，也不是 Codex Skill。
```

### 8.2 和 MCP Tool 的区别

```text
Diagnosis Skill 决定怎么诊断，MCP Tool 负责具体查数据。比如 data_volume_drop Skill 会要求必须查数据量趋势、任务状态、分区和血缘；真正执行查询的是 query_data_volume、query_task_runs、query_table_partitions 和 query_lineage 这些 MCP Tool。
```

### 8.3 为什么这样设计

```text
这样做的好处是可解释和可扩展。新增一个故障类型时，不需要重写 Agent 主流程，只要新增一个 Skill 目录，定义 triggers、required_tools、evidence_requirements 和 runbook。
```

## 9. RAG 怎么讲

推荐表达：

```text
RAG 在这个项目里不是用来泛泛问答，而是给诊断流程提供知识依据。它检索的是 Runbook、表口径说明、数据质量规则和历史事故复盘。最终报告必须展示 source_file、section_title 和 chunk_id，避免模型说不清依据。
```

如果问 RAG 召回错怎么办：

```text
我做了 metadata filter，例如按 skill_name、table_name、doc_type 限制候选文档，再做 top-k 检索。同时用 eval case 检查对应场景能否召回正确 Runbook。如果没有召回相关文档，报告里会明确说明知识依据不足。
```

## 10. MCP 怎么讲

推荐表达：

```text
MCP Tool 用来把外部系统查询能力标准化暴露给 Agent。MVP 中底层是 SQLite 模拟数据，但工具接口设计成 provider 抽象。真实环境下可以把 query_task_runs 接到 Airflow API，把 query_lineage 接到 DataHub，把 query_null_rate 接到数据质量平台。
```

如果问为什么要 MCP：

```text
MCP 的价值是把工具调用和 Agent 解耦。Agent 不需要知道底层是 SQLite 还是 Airflow，只需要知道工具 schema、参数和返回结构。
```

## 11. LangGraph 怎么讲

推荐表达：

```text
我用 LangGraph 是因为诊断流程不是单轮问答，而是多节点、有分支、有状态的流程。比如 AlertParser 之后可能进入澄清，CoverageChecker 发现工具缺失后可能回到 ToolExecutor 补查，最后再进入 Reporter。
```

节点顺序：

```text
AlertParser -> DiagnosisSkillMatcher -> KnowledgeRetriever -> Planner -> ToolExecutor -> CoverageChecker -> Reporter -> IncidentRecorder
```

## 12. 最推荐演示的案例

### 12.1 输入

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

### 12.2 演示顺序

1. 展示匹配到 `data_volume_drop`。
2. 展示 RAG 召回 `data_volume_drop.md` 和 `dws_sales_daily.md`。
3. 展示工具调用：
   - `query_data_volume`
   - `query_task_runs`
   - `query_table_partitions`
   - `query_lineage`
4. 展示 CoverageChecker。
5. 展示最终报告。
6. 追问：

```text
它影响哪些下游报表？
```

7. 展示系统基于 Session State 回答。

### 12.3 这条演示为什么最好

```text
数据量突降能展示最多技术点：Skill 匹配、RAG、MCP Tool、工具覆盖率、血缘影响、多轮状态和报告生成。
```

## 13. 常见追问和回答

### Q1：这个项目和普通 RAG Chatbot 有什么区别？

```text
普通 RAG Chatbot 主要是问答，核心是检索文档后回答。我的项目是诊断工作流，RAG 只是其中一环。系统还会匹配 Diagnosis Skill、调用 MCP Tool 查询事实、检查工具和证据覆盖率，并保存 incident 报告。
```

### Q1.5：这个项目是 Multi-Agent 吗？

```text
严格说当前版本不是 Multi-Agent，而是 single-agent workflow。它只有一个共享 DiagnosisState，由 LangGraph 编排多个可观察节点，例如 AlertParser、SkillMatcher、KnowledgeRetriever、Planner、ToolExecutor、CoverageChecker 和 Reporter。DeepSeek 会参与部分决策节点，但系统没有多个独立 Agent 实例，也没有 Agent-to-Agent 通信。这个阶段我优先保证工具证据链、CoverageChecker 和测试可控；后续如果扩展 Multi-Agent，可以拆成 Triage Agent、Evidence Agent、Knowledge Agent、Reporter Agent 和 Reviewer Agent。
```

### Q2：Diagnosis Skill 是不是你硬加的概念？

```text
不是。它对应真实排障里的 Runbook Playbook。不同故障类型需要不同证据，例如数据量突降要查行数趋势和血缘，空值率异常要查字段质量和字段来源。把这些策略配置成 Skill，可以避免把所有逻辑塞进一个 Prompt。
```

### Q3：为什么不用真实 Airflow？

```text
当前项目目标是验证 Agent 诊断链路，所以我用 SQLite 模拟任务、分区、质量和血缘数据，保证演示和测试可复现。工具层做了 provider 抽象，真实环境可以把 query_task_runs 替换为 Airflow API，不需要重写主工作流。
```

### Q4：系统选错 Skill 怎么办？

```text
我没有让模型直接自由选择工具。系统先用规则型 Diagnosis Skill Matcher，根据 triggers、symptoms 和 examples 计算置信度；如果配置了 DeepSeek，它可以辅助选择 Skill，但只能从内置 Skill 列表里选，且低置信度时仍会进入澄清。规则结果保留为 fallback。
```

### Q5：工具没查全怎么办？

```text
每个 Diagnosis Skill 都定义 required_tools 和 evidence_requirements。CoverageChecker 会对比实际 tool_calls，缺少关键工具时补查或降低报告置信度，报告里也会说明证据不足。
```

### Q6：RAG 召回错怎么办？

```text
我用 metadata filter 限制 skill_name、table_name 和 doc_type，再做 top-k 检索。报告必须展示引用来源。如果没有召回足够相关文档，报告会说明知识依据不足，而不是假装引用了 Runbook。
```

### Q7：多轮对话怎么处理？

```text
我没有只依赖聊天历史，而是保存结构化 Session State，包括 current_table、incident_id、selected_diagnosis_skill 和 evidence_summary。用户追问“它影响谁”时，系统会从当前 incident 状态中解析“它”。
```

### Q8：项目里你觉得最难的点是什么？

推荐回答：

```text
最难的不是调用模型，而是约束模型。比如工具没查全时模型可能直接下结论，所以我加了 CoverageChecker；告警描述模糊时模型可能选错 Skill，所以我加了候选 Skill 和澄清流程；多轮追问时模型容易丢上下文，所以我加了结构化 Session State。
```

### Q9：你怎么证明项目有效？

```text
我设计了三类验证：第一是单元测试，覆盖 Skill loader、matcher、CoverageChecker 和 SQLite provider；第二是端到端 smoke test，覆盖 4 个故障场景；第三是 eval case，统计 Skill 匹配准确率、工具覆盖率和 RAG 引用命中率。
```

### Q10：你对大数据组件不熟怎么办？

诚实回答：

```text
我没有把项目做成大数据平台本身，而是聚焦 DataOps 故障诊断流程。Airflow、分区、血缘、数据质量这些概念我在项目中只取了和诊断相关的部分，并用 SQLite 模拟。我的重点是 AI 应用开发能力：工作流编排、工具调用、RAG、状态管理和评估。
```

## 14. 简历项目描述

### 14.1 精简版

```text
DataOps OnCall Agent：基于 FastAPI、LangGraph、DeepSeek、RAG 和 MCP 设计数据平台故障诊断 single-agent workflow，支持任务失败、分区缺失、数据量突降、字段空值率异常等场景，完成 Diagnosis Skill 匹配、Runbook 检索、工具调用、证据覆盖检查、多轮状态管理和事故报告生成。
```

### 14.2 详细版

```text
设计并实现 DataOps OnCall Agent，将数据平台常见故障如 Airflow 任务失败、表分区缺失、数据量突降、字段空值率异常抽象为可插拔 Diagnosis Skill。系统基于 LangGraph 编排单 Agent 诊断流程，DeepSeek 参与告警解析、Skill 路由、规划和报告摘要，通过 RAG 检索 Runbook 和历史事故，通过 MCP Tool 查询 SQLite 模拟的数据平台元数据，最终生成带证据链的事故报告。
```

### 14.3 挑战版

```text
针对 Agent 在诊断场景中容易出现的 Skill 路由错误、工具调用不完整、RAG 误召回和长对话状态丢失问题，设计候选 Skill + 置信度澄清机制、CoverageChecker、带 metadata 的 RAG 检索和结构化 Session State，并用 eval case 统计 Skill 匹配准确率、工具覆盖率和 RAG 引用命中率。
```

## 15. 面试展示顺序

面试时如果有 5 到 8 分钟展示，按这个顺序：

1. 打开首页，展示 4 个 demo scenarios。
2. 选择数据量突降案例。
3. 点击开始诊断。
4. 展示 Skill 匹配结果。
5. 展示工具调用过程。
6. 展示 CoverageChecker。
7. 展示最终报告。
8. 追问“它影响哪些下游报表？”。
9. 展示 Session State 的效果。
10. 打开 docs/challenges-and-solutions.md 讲一个挑战。

配套演示脚本：

```text
docs/demo-script.md
```

## 16. 不要踩的坑

不要说：

```text
这是一个 Multi-Agent 系统。
```

应该说：

```text
当前版本是 single-agent workflow，不是 Multi-Agent。它用 LangGraph 把一个诊断 Agent 拆成多个可观察节点，后续可以扩展为多个专职 Agent。
```

不要说：

```text
我接入了真实生产数据平台。
```

应该说：

```text
我用 SQLite 模拟数据平台元数据，重点验证 Agent 诊断链路。真实接入可以通过 provider 替换。
```

不要说：

```text
模型可以自动判断所有故障。
```

应该说：

```text
模型判断需要约束。我用 Diagnosis Skill、CoverageChecker 和证据引用限制模型随意发挥。
```

不要说：

```text
Skill 就是工具。
```

应该说：

```text
Diagnosis Skill 是诊断策略，MCP Tool 才是具体查询动作。
```

## 17. 你自己的学习补位话术

如果面试官发现你对大数据组件没有实际生产经验，可以这样说：

```text
我确实没有真实生产数据平台经验，所以项目里没有假装接入真实 Airflow 或 Hive。我把重点放在 AI 应用开发岗位更关注的部分：如何把一个业务诊断流程拆成 Agent workflow，如何设计工具 schema，如何做 RAG 引用和状态管理，如何避免 Agent 工具没查全就输出结论。对于 Airflow、分区、血缘这些概念，我在项目里用最小可复现数据模型表达，后续可以接真实平台 API。
```

这个回答比硬装熟悉大数据更稳。

## 18. 最终主线

你整场面试要反复围绕这条主线：

```text
这个项目不是为了堆 Agent 热词，而是把数据故障诊断这个有真实约束的场景拆成可执行、可观察、可评估的 Agent 工作流。Diagnosis Skill 负责策略，RAG 负责知识，MCP Tool 负责证据，LangGraph 负责编排，CoverageChecker 负责约束，Session State 负责多轮上下文。
```

## 19. 当前实现结果

项目目前已经完成 B0 到 B9 的 MVP 闭环：

```text
FastAPI 接口：已完成
Demo UI：已完成，访问 http://localhost:9900
4 个 MVP 场景：均可端到端诊断
多轮追问：支持基于 Session State 回答下游影响
测试：43 passed
Skill match eval：accuracy = 1.0
RAG eval：hit_rate = 1.0
Tool coverage eval：tool_coverage = 1.0
真实模型验证：DeepSeek 决策节点 success，阿里云 text-embedding-v4 hybrid retrieval 已跑通
```

面试中要加一句边界说明：

```text
这些指标来自当前固定 MVP 数据集，用于证明工程链路可运行和可评估；它不等价于真实生产泛化效果。真实接入后需要扩展 eval cases 和 provider。
```

## 20. 最终 README 入口

讲解或投递时优先让对方看：

```text
README.md
docs/demo-script.md
docs/09-challenges-and-solutions.md
```
