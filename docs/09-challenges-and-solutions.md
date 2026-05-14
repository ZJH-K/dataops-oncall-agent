# 09 Challenges and Solutions - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：04-technical-design.md、07-test-cases.md

## 1. 文档目标

本文档记录 DataOps OnCall Agent 中最值得面试讲解的工程挑战和解决方案。它不是为了包装项目，而是为了让项目真正能扛住追问。

重要说明：

> 本文档已按当前 MVP 实现更新。当前版本使用 SQLite 模拟数据平台，使用规则型 Diagnosis Skill Matcher、可选 DeepSeek 决策辅助、轻量本地 RAG、可选阿里云 text-embedding-v4 hybrid retrieval、SQLite Tool Provider、LangGraph single-agent 工作流和 CoverageChecker。真实生产数据平台接入仍属于后续扩展。

面试中不要说“所有问题都完美解决了”，更好的说法是：

> 我围绕 Agent 项目常见的几个风险点做了约束设计，例如 Skill 路由、工具覆盖率、RAG 引用、多轮状态和模拟数据迁移。实现后我用测试和 eval 验证这些约束是否有效。

## 2. 挑战总览

| ID | 挑战 | 影响 | 解决方向 | 面试价值 |
|----|------|------|----------|----------|
| C-001 | Diagnosis Skill 路由错误 | 进入错误诊断流程 | 规则匹配 + 置信度 + 澄清 | 展示 Agent 路由设计 |
| C-002 | 工具调用不完整 | 缺证据却下结论 | required_tools + CoverageChecker | 展示工程约束 |
| C-003 | RAG 召回错误 | 引用错误 Runbook | metadata filter + 引用来源 + eval | 展示 RAG 可靠性 |
| C-004 | 长对话上下文丢失 | 多轮追问答非所问 | 结构化 Session State | 展示状态管理 |
| C-005 | 模型幻觉和过度确定 | 报告看似合理但没证据 | 证据绑定 + 置信度限制 | 展示安全输出 |
| C-006 | 模拟数据被认为太假 | 面试可信度下降 | seed 场景 + provider 抽象 | 展示边界意识 |
| C-007 | LLM 输出不稳定 | 测试难写 | 测结构化结果，不测全文 | 展示测试策略 |
| C-008 | 业务概念不熟 | 面试讲不深 | 聚焦 4 个场景 + 概念文档 | 展示学习路径 |
| C-009 | 被误解为 Multi-Agent | 面试定位不清 | single-agent workflow 边界 + 演进方案 | 展示诚实边界 |

## 3. C-001 Diagnosis Skill 路由错误

### 3.1 问题描述

用户输入的告警可能不完整或模糊。比如：

```text
今天销售报表不太对，帮我看看。
```

这个输入可能对应：

- 分区缺失。
- 数据量突降。
- 字段空值率异常。
- 上游任务失败。

如果 Agent 强行选择一个 Skill，后续诊断链路就会整体跑偏。

### 3.2 影响

- 工具调用方向错误。
- RAG 检索错误 Runbook。
- 最终报告根因错误。
- 面试官追问时容易暴露项目只是 Prompt Demo。

### 3.3 解决方案

当前 MVP 默认采用确定性规则匹配，并在 `LLM_PROVIDER=deepseek` 时引入 DeepSeek 辅助判断：

1. 从每个 `skill.yaml` 读取 `triggers`、`symptoms`、Skill name 和 examples。
2. 根据命中的触发词、症状词和示例计算 score。
3. DeepSeek 可以辅助解析告警和选择 Skill，但只能从内置 Skill 列表中选择。
4. 最高分低于阈值，或模型输出无效时，不进入诊断，而是请求澄清或回退规则结果。

```text
if top_skill_confidence < 0.65:
    return needs_clarification
```

### 3.4 实现要点

每个 `skill.yaml` 提供：

```yaml
triggers:
  - 数据量下降
  - 行数变少
  - 环比下降
symptoms:
  - data_volume_drop
examples: examples.json
```

Matcher 输出：

```json
{
  "selected_diagnosis_skill": {
    "name": "data_volume_drop",
    "confidence": 0.91,
    "reason": "用户明确描述今日数据量较昨日下降 92%。"
  },
  "candidate_diagnosis_skills": []
}
```

### 3.5 测试方式

- 准备覆盖 4 个 MVP 场景的 Skill match eval cases。
- 验证 4 个明确告警能匹配正确。
- 验证模糊告警进入澄清。

### 3.6 实际实现记录

- 修改文件：`app/skills/loader.py`、`app/skills/matcher.py`、`app/skills/builtin/*/skill.yaml`。
- 验证文件：`tests/test_skill_loader.py`、`tests/test_skill_matcher.py`、`eval/datasets/skill_match_cases.jsonl`。
- 当前结果：`skill_match_cases` accuracy = 1.0。
- 剩余限制：DeepSeek 只参与受约束的 Skill 选择，不负责自由创造新诊断策略；规则结果保留为可解释 fallback。

### 3.7 面试讲法

```text
我没有让模型直接自由选择工具，而是先通过 Diagnosis Skill metadata 做确定性匹配。配置 DeepSeek 后，模型可以辅助解析和路由，但只能选择内置 Skill；低置信度或输出无效时系统会请求澄清或回退规则结果。这样可以降低错误路由导致的误诊，也方便测试和面试解释。
```

## 4. C-002 工具调用不完整

### 4.1 问题描述

Agent 可能只调用了一个工具就开始生成报告。例如数据量突降场景中，只查了 `query_data_volume`，没有查任务状态、分区和血缘。

### 4.2 影响

- 只能证明行数下降，不能解释为什么下降。
- 缺少下游影响范围。
- 报告容易过度推断。

### 4.3 解决方案

每个 Diagnosis Skill 定义：

```yaml
required_tools:
  - query_data_volume
  - query_task_runs
  - query_table_partitions
  - query_lineage
evidence_requirements:
  - recent_row_count_trend
  - related_task_status
  - current_partition_status
  - downstream_impact
```

CoverageChecker 对照实际调用结果输出：

```json
{
  "required_tools_coverage": 0.75,
  "missing_tools": ["query_lineage"],
  "confidence_limit": "medium"
}
```

### 4.4 决策规则

- 缺少关键工具且工具可用：补充调用。
- 工具失败：生成降级报告。
- 证据不足：报告中明确说明不可确认部分。

### 4.5 测试方式

- 构造缺少 `query_lineage` 的 tool_calls。
- 断言 CoverageChecker 能识别 missing_tools。
- 断言报告包含“无法确认完整下游影响范围”。

### 4.6 实际实现记录

- 修改文件：`app/workflow/nodes/coverage_checker.py`、`app/workflow/nodes/tool_executor.py`。
- 验证文件：`tests/test_coverage_checker.py`、`tests/test_workflow_smoke.py`、`eval/datasets/tool_coverage_cases.jsonl`。
- 当前结果：`tool_coverage_cases` tool_coverage = 1.0。
- 行为结果：缺少工具时 CoverageChecker 会返回 `action=retry_tools`；重试后仍缺证据时报告状态降级为 `partial` 并设置 `confidence_limit`。

### 4.7 面试讲法

```text
我把 required_tools 写进 Diagnosis Skill，再用 CoverageChecker 做约束检查。这样模型不能查一个工具就下结论，报告生成前会检查工具覆盖率和证据覆盖率。
```

## 5. C-003 RAG 召回错误

### 5.1 问题描述

RAG 可能召回不相关 Runbook。例如用户问数据量突降，却召回 SQL 执行失败文档。

### 5.2 影响

- Planner 生成错误步骤。
- 报告引用错误依据。
- 面试中容易被问“你的 RAG 怎么保证准确”。

### 5.3 解决方案

RAG 检索默认使用 metadata filter：

```json
{
  "skill_name": "data_volume_drop",
  "table_name": "dws_sales_daily",
  "doc_type": ["runbook", "table_doc", "postmortem"]
}
```

同时要求返回：

- `source_file`
- `section_title`
- `chunk_id`
- `score`

如果配置 `EMBEDDING_PROVIDER=aliyun`，构建索引时会调用阿里云百炼 `text-embedding-v4` 写入向量；检索时使用 keyword/metadata score + embedding cosine similarity 的 hybrid scoring。

### 5.4 报告约束

如果没有召回相关文档，报告不能写：

```text
根据 Runbook 可知...
```

只能写：

```text
本次未检索到足够相关 Runbook，结论主要基于工具查询证据。
```

### 5.5 测试方式

- `data_volume_drop` 查询 top 3 必须包含 `runbooks/data_volume_drop.md`。
- `null_rate_spike` 查询 top 3 必须包含空值率相关文档。
- 无关查询应返回空或低分结果。

### 5.6 实际实现记录

- 修改文件：`scripts/build_rag_index.py`、`app/rag/retriever.py`。
- 验证文件：`tests/test_rag_retriever.py`、`eval/datasets/rag_cases.jsonl`。
- 当前结果：`rag_cases` hit_rate = 1.0。
- 行为结果：检索结果返回 `source_file`、`doc_type`、`section_title`、`skill_name`、`table_name`、`chunk_id`、`score` 和 `retrieval_mode`。真实验证中阿里云 `text-embedding-v4` 返回 1024 维向量，41 个 RAG chunk 已可构建 hybrid index。

### 5.7 面试讲法

```text
我没有只做纯向量检索，而是把 skill_name、table_name、doc_type 放进 metadata，用它先缩小检索范围。配置阿里云 embedding 后再做 hybrid scoring。报告里也必须展示引用来源，避免模型说不清依据。
```

## 6. C-004 长对话上下文丢失

### 6.1 问题描述

用户完成一次诊断后可能追问：

```text
它影响哪些下游报表？
```

如果系统只依赖聊天历史，长对话时可能不知道“它”指的是哪张表或哪次事故。

### 6.2 解决方案

保存结构化 Session State：

```json
{
  "session_id": "session-001",
  "incident_id": "incident-20260514-001",
  "current_table": "dws_sales_daily",
  "selected_diagnosis_skill": "data_volume_drop",
  "evidence_summary": {
    "downstream_tables": ["ads_sales_report"]
  }
}
```

追问时优先读取 state，而不是只把聊天历史塞给模型。

### 6.3 测试方式

- 完成一次数据量突降诊断。
- 发送“它影响哪些下游报表？”。
- 断言回答引用当前 incident 的 lineage 证据。

### 6.4 实际实现记录

- 修改文件：`app/workflow/nodes/incident_recorder.py`、`app/api/services.py`。
- 验证文件：`tests/test_api_diagnose.py`。
- 行为结果：诊断完成后会把 `current_table`、`selected_diagnosis_skill`、`incident_id` 和 state snapshot 写入 `sessions`，`POST /api/chat` 使用这些状态回答追问。

### 6.5 面试讲法

```text
多轮记忆不是简单保存聊天记录。我把当前 incident、表名、字段、Skill 和证据摘要结构化保存，后续追问优先读取 Session State。这样能解决长对话中指代丢失的问题。
```

## 7. C-005 模型幻觉和过度确定

### 7.1 问题描述

模型可能在证据不足时输出很确定的根因，比如：

```text
根因一定是上游支付订单同步失败。
```

但实际上可能没有查到任务状态或血缘证据。

### 7.2 解决方案

Reporter 生成报告时必须绑定证据：

- 工具结果。
- RAG 引用。
- CoverageChecker 结果。

如果 confidence_limit 为 `medium` 或 `low`，报告应该使用谨慎表达：

```text
初步判断可能与支付订单同步任务失败有关，但由于血缘查询失败，无法确认完整影响范围。
```

### 7.3 测试方式

- 构造工具失败场景。
- 验证报告包含证据不足说明。
- 验证报告不出现“确定”“一定”等过度措辞。

### 7.4 实际实现记录

- 修改文件：`app/workflow/nodes/reporter.py`、`app/workflow/nodes/coverage_checker.py`。
- 验证文件：`tests/test_workflow_smoke.py`。
- 行为结果：最终报告固定包含 RAG 引用来源、工具调用证据、CoverageChecker 和证据不足说明；未知表数据量下降场景会生成受限结论。

### 7.5 面试讲法

```text
我把报告结论和证据绑定，证据不足时限制结论置信度。这个设计是为了减少 Agent 在运维诊断场景中过度自信的问题。
```

## 8. C-006 模拟数据被认为太假

### 8.1 问题描述

项目使用 SQLite 模拟数据平台，面试官可能质疑这不是真实生产系统。

### 8.2 正确边界

不能说：

```text
我接入了真实 Airflow 和数仓。
```

应该说：

```text
当前演示环境使用 SQLite 模拟数据平台元数据，重点验证 Agent 诊断链路。真实环境中可以把 SQLite provider 替换成 Airflow API、Hive Metastore、DataHub 或数据质量平台。
```

### 8.3 解决方案

- seed 脚本生成稳定故障场景。
- MCP Tool 隔离底层数据源。
- provider interface 抽象真实系统。
- demo scenarios 记录期望根因和期望工具。

### 8.4 面试讲法

```text
我没有把模拟数据包装成真实生产经历，而是把它作为可复现测试环境。Agent 主流程不依赖 SQLite，只依赖 MCP Tool 的结构化返回。真实环境迁移时替换 provider，不需要重写 LangGraph 工作流。
```

### 8.5 实际实现记录

- 修改文件：`app/db/demo_seed.py`、`scripts/reset_demo_data.py`、`scripts/seed_demo_data.py`、`app/tools/providers/sqlite_provider.py`。
- 当前数据：4 个 demo scenarios，覆盖任务失败、分区缺失、数据量突降、空值率异常。
- 当前边界：MCP Server 以本地 JSON CLI 形式提供工具入口，FastAPI 直接调用 provider 层；真实远程 MCP 服务不是本 MVP 的重点。

## 9. C-007 LLM 输出不稳定导致测试困难

### 9.1 问题描述

LLM 生成的自然语言报告每次可能不完全一致。

### 9.2 解决方案

测试不强依赖全文一致，而是验证结构化字段和关键事实：

- selected_diagnosis_skill。
- called_tools。
- coverage_result。
- incident_id。
- report 是否包含关键证据关键词。

### 9.3 测试方式

```python
assert result.selected_diagnosis_skill == "data_volume_drop"
assert "query_data_volume" in called_tools
assert "dws_sales_daily" in final_report
assert "引用来源" in final_report
```

### 9.4 面试讲法

```text
我没有用全文快照测试 LLM 输出，而是测试结构化结果和关键证据。这样可以适应模型输出的自然波动，同时保证业务结论可验证。
```

### 9.5 实际实现记录

- 验证文件：`tests/test_workflow_smoke.py`、`tests/test_api_diagnose.py`、`tests/test_coverage_checker.py`。
- 当前结果：全量 pytest 43 passed。
- 断言重点：`selected_diagnosis_skill`、`tool_calls`、`coverage_result`、`incident_id`、报告中的 RAG 来源和工具证据。

## 10. C-008 业务概念不熟

### 10.1 问题描述

DataOps 场景涉及 Airflow、分区、血缘、数据质量等概念。如果理解不深，面试中容易讲虚。

### 10.2 解决方案

项目聚焦 4 个最容易讲清楚的故障：

- Airflow 任务失败。
- 表分区缺失。
- 数据量突降。
- 字段空值率异常。

每个场景都准备：

- 人话解释。
- 示例告警。
- seed 数据。
- 期望工具。
- 期望报告。
- 面试讲法。

### 10.3 面试讲法

```text
我没有试图覆盖整个大数据体系，而是围绕 4 个典型 DataOps 故障做深。每个场景都能解释清楚故障是什么、该查什么证据、工具怎么返回、报告怎么生成。
```

## 11. C-009 被误解为 Multi-Agent

### 11.1 问题描述

项目名称里有 Agent，流程里又有 AlertParser、Planner、Reporter 等多个节点，面试官可能会问这是不是 Multi-Agent。

### 11.2 正确边界

当前版本不是 Multi-Agent，而是 single-agent workflow：

- 只有一个共享 `DiagnosisState`。
- LangGraph 节点是流程阶段，不是独立 Agent 实例。
- 没有 Agent-to-Agent 通信。
- 没有多个 Agent 分别持有独立目标、记忆和工具集。

### 11.3 为什么暂不做 Multi-Agent

当前项目目标是求职面试用 MVP，最重要的是可运行、可观察、可测试。DataOps 诊断链路本身已经包含 Skill 路由、RAG、工具调用、证据覆盖和报告约束。如果过早拆成多个 Agent，会增加调试和评估复杂度，但不一定提升演示价值。

### 11.4 后续演进方案

后续可以拆成：

- Triage Agent：解析告警并选择 Diagnosis Skill。
- Evidence Agent：调用 MCP Tool 收集证据。
- Knowledge Agent：负责 RAG 检索和 Runbook 解释。
- Reporter Agent：生成事故报告。
- Reviewer Agent：检查证据覆盖和过度结论。

### 11.5 面试讲法

```text
当前版本不是 Multi-Agent，而是一个 single-agent workflow。我用 LangGraph 把一个诊断 Agent 拆成多个可观察节点，先保证证据链、CoverageChecker 和测试稳定。后续如果要扩展 Multi-Agent，可以按 Triage、Evidence、Knowledge、Reporter、Reviewer 拆分。
```

## 12. 开发后需要补充的真实记录

每个挑战实现后，需要补充：

```text
问题复现：输入是什么，错误表现是什么。
定位过程：看了哪些日志、状态或测试。
修改方案：改了哪个模块。
验证结果：新增了什么测试，指标有没有提升。
剩余限制：还有什么没解决。
```

示例模板：

```markdown
### 实际问题记录

- 复现输入：
- 错误表现：
- 定位过程：
- 修改文件：
- 新增测试：
- 修复前结果：
- 修复后结果：
- 剩余限制：
```

## 13. 最值得写进简历的挑战

推荐简历或面试重点讲这 4 个：

1. Diagnosis Skill 路由错误。
2. 工具调用不完整。
3. RAG 召回和引用可靠性。
4. 多轮 Session State。

简历表述示例：

```text
针对 Agent 在数据故障诊断中容易出现的路由错误、工具调用不完整、RAG 误召回和长对话状态丢失问题，设计 Diagnosis Skill Matcher、CoverageChecker、带 metadata 的 RAG 检索和结构化 Session State，使诊断报告能够关联工具证据和引用来源。
```

## 14. 当前验证结果

```text
uv --cache-dir .uv-cache run pytest tests -q
43 passed

uv --cache-dir .uv-cache run python eval/run_eval.py --dataset skill_match_cases
accuracy = 1.0

uv --cache-dir .uv-cache run python eval/run_eval.py --dataset rag_cases
hit_rate = 1.0

uv --cache-dir .uv-cache run python eval/run_eval.py --dataset tool_coverage_cases
tool_coverage = 1.0

真实模型验证：
DeepSeek 在 AlertParser、DiagnosisSkillMatcher、Planner 节点返回 success
阿里云 text-embedding-v4 已构建 41 个 chunk 的 hybrid RAG index
```

这些指标只代表当前固定 MVP 数据集，不代表真实生产环境泛化能力。面试中应诚实说明：当前项目证明的是诊断架构、工具证据链和评估方法可运行，真实系统接入后仍需要扩展数据集和 provider。
