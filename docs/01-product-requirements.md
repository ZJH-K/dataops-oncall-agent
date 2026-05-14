# 01 Product Requirements - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
项目定位：面向求职面试的 DataOps Agent 应用项目
目标岗位：AI 应用开发工程师 / Agent 应用开发工程师 / 大模型应用开发工程师 / Python 后端开发

## 1. 项目概述

DataOps OnCall Agent 是一个面向数据平台值班场景的智能故障诊断系统。系统接收数据任务、数据表、数据质量或指标异常类告警后，会自动识别故障类型，匹配对应的 Diagnosis Skill，加载 Runbook 和知识库资料，通过 MCP 工具查询任务运行、表分区、数据量、字段质量和血缘依赖等模拟数据，最终生成带证据链的事故诊断报告。

本项目的核心目标不是做一个功能堆满的通用聊天机器人，而是做一个能在面试中讲清楚工程深度的 Agent 应用：围绕 Diagnosis Skill 路由、RAG 可靠性、MCP 工具调用、工具覆盖率、多轮诊断状态和事故报告生成，展示一个完整、可演示、可追问的数据故障诊断闭环。
### 1.1 术语边界：本项目中的 Diagnosis Skill 是什么

本项目中的 `Diagnosis Skill` 不是 Codex 的本地 skill，也不是 MCP Tool，而是一种运行时业务抽象：**面向某一类数据故障的可配置诊断策略包**。

它的职责是告诉 Agent：当前故障应该如何识别、应该查哪些证据、必须调用哪些工具、需要参考哪些 Runbook、最终报告应该包含什么。它不直接查询数据库，也不直接执行外部动作。

四个核心概念的边界如下：

| 概念 | 项目中的职责 | 示例 |
|------|--------------|------|
| Diagnosis Skill | 定义某类故障的诊断策略和证据要求 | `data_volume_drop` 要求查询行数趋势、任务状态、分区和血缘 |
| Runbook / RAG | 提供排查知识、历史经验和表说明 | 检索 `data_volume_drop.md`、历史事故复盘、表口径文档 |
| MCP Tool | 执行具体查询或写入动作 | `query_data_volume`、`query_task_runs`、`query_lineage` |
| LangGraph Workflow | 编排诊断流程和状态流转 | AlertParser -> DiagnosisSkillMatcher -> ToolExecutor -> Reporter |

因此，面试中可以直接使用 `Diagnosis Skill` 这个说法，并解释它类似一个 Runbook Playbook：定义某类故障的触发条件、证据要求、必需工具和输出格式。不要把它说成工具、Prompt 或 Codex Skill。

## 2. 背景与问题

数据平台在日常运行中经常出现任务失败、分区缺失、数据量异常、字段空值率异常、指标波动等问题。真实企业里，这类问题通常需要数据开发或值班人员手动排查多个系统：调度平台、任务日志、表元数据、数据质量平台、血缘系统和历史事故文档。

对初级 AI 应用开发求职者来说，普通 RAG 问答项目和网上售卖的 Agent 项目容易出现简历雷同，且难以体现真实工程问题。本项目选择 DataOps OnCall 场景，是因为它同时满足三个条件：

- 与数据科学与大数据技术专业背景相关，面试解释更自然。
- 场景有明确业务约束，适合展示 Agent 的工具调用和状态管理能力。
- 可以用 SQLite 和脚本生成模拟数据，不依赖真实企业系统，也能复现典型故障。

## 3. 产品目标

### 3.1 面试目标

本项目优先服务于求职面试，要求做到：

- 能本地一键启动并完成完整演示。
- 能覆盖 4 类典型 DataOps 故障。
- 能解释为什么使用 RAG、MCP、Diagnosis Skills 和 LangGraph。
- 能展示遇到过的工程问题及解决方案。
- 能支撑简历中关于 Agent 应用开发、RAG、工具调用、状态管理和评估的描述。

### 3.2 业务目标

在演示环境中，系统应能帮助值班人员快速回答：

- 这次告警属于什么类型？
- 应该使用哪个 Diagnosis Skill？
- 需要查询哪些任务、表、分区、质量规则和血缘信息？
- 当前证据是否足够支持根因判断？
- 影响了哪些下游表或报表？
- 最终事故报告应该如何生成？

### 3.3 技术目标

系统需要体现以下技术能力：

- FastAPI 后端服务设计。
- LangGraph 多节点 Agent 工作流编排。
- RAG 检索 Runbook、表说明、历史事故复盘。
- MCP Server 暴露数据平台查询工具。
- Diagnosis Skill Center 管理可插拔的故障诊断策略。
- SQLite 模拟数据平台元数据和故障数据。
- 结构化 Session State 保存多轮诊断上下文。
- Tool Coverage Checker 检查必需工具调用是否完整。
- 基础 eval/test 证明系统不是纯 Demo。

## 4. 用户与使用场景

### 4.1 目标用户

主要用户：数据开发工程师、数据平台值班人员、数据质量治理人员。

面试叙述中的用户可以定义为：

> 一名数据开发在早上收到销售日报数据异常告警，需要快速判断问题是任务失败、上游缺分区、数据量异常还是字段质量异常，并生成事故报告给业务方。

### 4.2 核心场景

MVP 阶段优先支持 4 个场景：

1. Airflow 任务失败

   示例告警：

   ```text
   DAG dwd_order_detail_daily 在今天凌晨运行失败，请帮我诊断原因。
   ```

2. 数据表今日分区缺失

   示例告警：

   ```text
   dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。
   ```

3. 数据量突降

   示例告警：

   ```text
   dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
   ```

4. 字段空值率异常

   示例告警：

   ```text
   ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。
   ```

后续扩展场景：SQL 执行失败、指标环比异常、Flink 任务延迟、Spark 任务耗时异常、历史事故相似案例召回。

## 5. 产品范围

### 5.1 MVP 必做范围

MVP 需要完成以下闭环：

```text
输入告警
  -> 解析告警上下文
  -> 匹配 Diagnosis Skill
  -> 检索 Runbook / 历史事故 / 表说明
  -> 生成诊断计划
  -> 调用 MCP 工具查询模拟数据
  -> 检查必需工具覆盖率
  -> 生成带证据的事故报告
  -> 保存诊断记录
```

### 5.2 暂不做范围

为了控制项目周期，MVP 阶段不做：

- 不接入真实 Airflow、Hive、Spark、Flink、DataHub 或企业日志平台。
- 不实现复杂权限系统。
- 不实现真实自动修复动作。
- 不训练或微调模型。
- 不做复杂多租户和企业级账号体系。
- 不追求完整生产级 UI，只做清晰可演示页面。

面试解释口径：

> 当前项目使用 SQLite 和 mock provider 模拟数据平台，重点验证 Agent 诊断流程。真实生产环境可以将 MCP 工具底层替换为 Airflow API、Hive Metastore、DataHub、Great Expectations、Prometheus 或内部数据质量平台。

## 6. 核心功能需求

### 6.1 告警输入与上下文解析

用户可以输入自然语言告警。系统需要提取：

- 表名，例如 `dws_sales_daily`。
- DAG 或任务名，例如 `dwd_order_detail_daily`。
- 故障类型候选，例如任务失败、分区缺失、数据量突降、空值率异常。
- 时间范围，例如今天、昨天、最近 1 小时。
- 关键指标，例如下降 92%、空值率升高。

验收标准：

- 对 4 类 MVP 示例告警能解析出主要实体。
- 解析失败时能要求用户补充信息，而不是编造。

### 6.2 Diagnosis Skill Center

系统需要内置可插拔的 DataOps Diagnosis Skill。每个 Diagnosis Skill 是一个可配置的故障诊断策略，至少包含：

- `skill.yaml`：名称、描述、触发词、必需工具、证据要求、风险等级、是否需要确认、输出格式。
- `runbook.md`：该类故障的排查流程，作为 RAG 可检索知识来源。
- `examples.json`：示例告警、期望匹配结果、期望根因。

MVP 内置 Diagnosis Skill：

- `airflow_task_failed`
- `partition_missing`
- `data_volume_drop`
- `null_rate_spike`

验收标准：

- `GET /api/skills` 能查看所有 Diagnosis Skill。
- 系统能根据告警匹配一个主 Diagnosis Skill，并返回匹配理由。
- 低置信度时返回候选 Diagnosis Skill，而不是强行选择。

### 6.3 RAG 知识检索

RAG 用于检索：

- Runbook。
- 表口径说明。
- 历史事故复盘。
- 数据质量规则说明。
- 常见 SQL/调度错误说明。

检索结果需要带来源信息：

- `source_file`
- `section_title`
- `chunk_id`
- `score`

验收标准：

- 诊断报告必须包含引用来源。
- 相关故障能召回对应 Runbook。
- 当检索结果不足时，系统需要提示证据不足。

### 6.4 MCP 工具调用

系统需要提供本地 MCP Server，用于把数据平台查询能力暴露给 Agent。MVP 工具包括：

- `query_task_runs`：查询任务运行状态。
- `query_table_partitions`：查询表分区是否产出。
- `query_data_volume`：查询表每日行数。
- `query_null_rate`：查询字段空值率。
- `query_lineage`：查询上下游血缘。
- `create_incident_report`：创建事故报告记录。

底层数据源为 SQLite 模拟库。

验收标准：

- 每个工具都能独立调用并返回结构化 JSON。
- Agent 诊断过程能记录每次工具调用的参数、返回结果摘要和状态。
- 工具异常时，最终报告需要说明失败原因。

### 6.5 LangGraph 诊断工作流

MVP 工作流建议拆分为以下节点：

```text
AlertParser
DiagnosisSkillMatcher
KnowledgeRetriever
Planner
ToolExecutor
CoverageChecker
Reporter
IncidentRecorder
```

状态字段至少包含：

- `session_id`
- `raw_alert`
- `alert_context`
- `selected_diagnosis_skill`
- `candidate_diagnosis_skills`
- `retrieved_docs`
- `plan`
- `tool_calls`
- `evidence`
- `coverage_result`
- `final_report`
- `incident_id`

验收标准：

- 单次诊断能完整流转到报告生成。
- 多轮对话中能保留当前诊断对象，例如表名、事故 ID、已获取证据。
- 长对话不只依赖模型聊天历史，而是依赖结构化状态。

### 6.6 Tool Coverage Checker

每个 Diagnosis Skill 定义 `required_tools` 和 `evidence_requirements`。系统在生成最终报告前，需要检查必需工具和关键证据是否都已覆盖。

示例：

```yaml
required_tools:
  - query_data_volume
  - query_task_runs
  - query_table_partitions
  - query_lineage
```

如果缺少关键工具，系统应：

- 自动补充执行缺失工具，或
- 在报告中明确说明证据不足。

验收标准：

- 对每个 MVP Diagnosis Skill 能输出工具覆盖率和证据覆盖情况。
- 报告中能看到本次诊断使用了哪些证据。
- 不允许在关键证据缺失时给出过度确定的根因。

### 6.7 事故报告生成

最终报告采用 Markdown，至少包含：

- 告警摘要。
- 匹配到的 Diagnosis Skill。
- 诊断步骤。
- 工具调用证据。
- 根因判断。
- 影响范围。
- 修复建议。
- 风险等级。
- 引用来源。
- 证据不足说明。

验收标准：

- 报告可直接展示在前端。
- 报告能保存到 SQLite。
- 报告中的关键结论必须能追溯到工具结果或 RAG 引用。

### 6.8 前端演示页面

前端以演示闭环为主，建议包含：

- 告警输入区。
- Diagnosis Skill 匹配结果。
- 诊断计划。
- 工具调用过程。
- 证据列表。
- 最终报告。
- 历史事故记录。

验收标准：

- 面试演示时能在 3 分钟内完成一次完整诊断。
- 页面不需要复杂，但流程必须清晰。

## 7. 非功能需求

### 7.1 可演示性

- 提供一键初始化模拟数据脚本。
- 提供固定演示案例。
- 提供 README 中的演示命令。
- 模型不可用时，至少能跑通工具层和测试用例。

### 7.2 可解释性

- Diagnosis Skill 匹配需要返回理由。
- 工具调用需要记录。
- 报告结论需要关联证据。
- RAG 引用需要展示来源。

### 7.3 可测试性

需要覆盖以下测试：

- Diagnosis Skill loader 测试。
- Diagnosis Skill matcher 测试。
- MCP tool 测试。
- SQLite seed data 测试。
- 诊断工作流 smoke test。
- 报告是否包含证据来源。

### 7.4 可扩展性

- Diagnosis Skill 可以通过新增目录扩展。
- MCP 工具底层 provider 可以替换。
- RAG 文档可以新增 runbook、postmortem 和 table docs。
- 故障场景可以通过 seed 脚本新增。

## 8. 成功指标

### 8.1 项目完成指标

- 支持 4 个 MVP 故障场景。
- 至少 4 个内置 Diagnosis Skill。
- 至少 6 个 MCP 工具。
- 至少 10 篇 Runbook / 表说明 / 历史事故文档。
- 至少 20 条 eval case。
- 至少 10 个核心测试用例。

### 8.2 Agent 质量指标

MVP 可用以下指标衡量：

- Diagnosis Skill 匹配准确率：目标 >= 85%。
- 必需工具覆盖率：目标 >= 90%。
- RAG 引用命中率：目标 >= 80%。
- 报告证据完整率：目标 >= 80%。
- 典型案例端到端诊断成功率：目标 >= 80%。

### 8.3 面试效果指标

项目需要能支持回答以下问题：

- 你为什么选择 DataOps OnCall 这个场景？
- 你的 Agent 和普通 RAG Chatbot 有什么区别？
- Diagnosis Skill 是怎么设计和匹配的？它和 MCP Tool 有什么区别？
- MCP 工具调用失败怎么办？
- RAG 召回错误怎么发现和优化？
- 多轮诊断状态如何保存？
- 工具没查全时怎么避免错误结论？
- 模拟数据和真实系统有什么差距？如何迁移到真实系统？

## 9. 典型用户故事

### Story 1：诊断任务失败

作为数据开发，我希望在 Airflow 任务失败后，系统能自动查询任务状态、失败日志、上下游依赖和相关 Runbook，帮助我快速判断失败原因并生成事故报告。

验收标准：

- 输入任务失败告警后，系统匹配 `airflow_task_failed` Diagnosis Skill。
- 系统调用 `query_task_runs` 和 `query_lineage`。
- 报告包含失败任务、失败时间、影响下游和处理建议。

### Story 2：诊断分区缺失

作为值班人员，我希望系统在发现某张表今日分区未产出时，能自动检查上游任务和上游表分区，判断是当前任务失败还是上游数据未就绪。

验收标准：

- 输入分区缺失告警后，系统匹配 `partition_missing` Diagnosis Skill。
- 系统调用 `query_table_partitions`、`query_task_runs`、`query_lineage`。
- 报告能区分当前表问题和上游表问题。

### Story 3：诊断数据量突降

作为数据质量负责人，我希望系统在发现表行数较昨日大幅下降时，能查询历史数据量、任务状态和血缘信息，判断是否影响下游报表。

验收标准：

- 输入数据量突降告警后，系统匹配 `data_volume_drop` Diagnosis Skill。
- 系统调用 `query_data_volume` 和 `query_lineage`。
- 报告包含下降比例、可能根因和影响范围。

### Story 4：诊断字段空值率异常

作为数据开发，我希望系统在字段空值率异常升高时，能定位异常字段、影响表、上游来源和可能业务影响。

验收标准：

- 输入空值率异常告警后，系统匹配 `null_rate_spike` Diagnosis Skill。
- 系统调用 `query_null_rate`、`query_lineage`。
- 报告包含异常字段、空值率变化、影响范围和建议处理方式。

## 10. 版本规划

### v0.1 文档与脚手架

- 完成 PRD、TRD、数据库设计、API 文档。
- 搭建 FastAPI 项目结构。
- 设计 SQLite schema。
- 设计 Diagnosis Skill 目录规范。

### v0.2 数据与工具层

- 完成 SQLite 初始化和 seed 数据。
- 完成 MCP Server。
- 完成核心查询工具。
- 完成工具调用日志。

### v0.3 Agent 工作流

- 完成 Diagnosis Skill Matcher。
- 完成 RAG 检索。
- 完成 LangGraph 诊断流程。
- 完成 Coverage Checker。

### v0.4 演示闭环

- 完成前端演示页面。
- 完成 4 个端到端案例。
- 完成事故报告保存。
- 完成 README 演示说明。

### v0.5 面试增强

- 完成 eval case。
- 完成核心测试。
- 完成 `challenges-and-solutions.md`。
- 完成 `interview-talking-points.md`。

## 11. 风险与应对

### 风险 1：业务概念不熟，面试讲不深

应对：项目只聚焦 4 个典型 DataOps 故障，并在文档中用人话解释 DAG、分区、血缘、数据质量、Runbook 等概念。

### 风险 2：项目被认为只是模拟数据 Demo

应对：强调项目目标是验证 Agent 诊断链路，模拟数据用于可复现演示；同时设计 provider 抽象，说明如何替换到真实 Airflow、Hive、DataHub 或数据质量平台。

### 风险 3：Agent 输出看起来像编造

应对：报告必须引用 MCP 工具结果或 RAG 来源；缺少证据时明确说明证据不足。

### 风险 4：功能太多导致做不完

应对：MVP 只做 4 个故障场景、4 个 Diagnosis Skill、6 个 MCP 工具；先完成闭环，再做扩展。

### 风险 5：简历表达过度包装

应对：简历中明确表达为“基于模拟数据平台实现 DataOps OnCall Agent 原型”，突出架构设计、工具调用、状态管理、评估和可扩展性，不虚构真实生产接入经历。

## 12. 面试定位总结

本项目在简历中的推荐表述：

> 设计并实现 DataOps OnCall Agent，将数据平台常见故障如 Airflow 任务失败、分区缺失、数据量突降、字段空值率异常抽象为可插拔 Diagnosis Skill。系统基于 FastAPI、LangGraph、RAG、MCP 和 SQLite 模拟数据平台，实现告警解析、Diagnosis Skill 匹配、Runbook 检索、工具调用、证据覆盖检查、多轮诊断状态管理和事故报告生成，并通过 eval case 评估 Diagnosis Skill 匹配准确率、工具覆盖率和 RAG 引用命中率。

项目最重要的面试讲解主线：

```text
我没有做一个普通聊天机器人，而是围绕 DataOps 故障诊断场景，设计了一个可追溯的 Agent 工作流。Diagnosis Skills 负责选择诊断策略和证据要求，RAG 负责提供 Runbook 和历史经验，MCP 负责查询外部系统证据，LangGraph 负责状态编排，Coverage Checker 负责避免工具没查全就下结论。
```


