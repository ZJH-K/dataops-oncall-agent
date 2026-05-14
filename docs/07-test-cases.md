# 07 Test Cases - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：04-technical-design.md、05-api-spec.md、06-database-schema.md

## 1. 测试目标

本项目的测试目标不是追求覆盖率数字好看，而是证明 DataOps OnCall Agent 的核心链路可靠：Diagnosis Skill 能匹配正确，MCP Tool 能查到证据，RAG 能召回相关 Runbook，CoverageChecker 能发现工具没查全，最终报告能引用证据。

测试需要服务于两个目标：

- 开发目标：每次改动后能确认核心诊断流程没有坏。
- 面试目标：能证明项目不是只靠 Prompt 拼出来的 Demo，而是有可验证的工程约束。

## 2. 测试范围

### 2.1 MVP 必测范围

- Diagnosis Skill loader。
- Diagnosis Skill matcher。
- SQLite seed data。
- MCP Tool 查询。
- RAG 检索。
- CoverageChecker。
- LangGraph workflow smoke test。
- API 基础接口。
- 多轮 Session State。
- 事故报告证据引用。

### 2.2 暂不覆盖范围

MVP 阶段暂不重点测试：

- 大规模并发。
- 企业级权限。
- 真实 Airflow、Hive、DataHub 接入。
- 复杂前端交互。
- LLM 输出逐字稳定性。

LLM 输出具有不确定性，所以测试应优先验证结构化结果和关键字段，不强依赖完整自然语言文本完全一致。

## 3. 测试分层

```text
Unit Tests
  -> Skill loader / matcher / CoverageChecker / provider 查询逻辑

Integration Tests
  -> MCP Tool + SQLite / RAG retriever / API endpoint

Workflow Smoke Tests
  -> 4 个 MVP 故障场景端到端诊断

Eval Cases
  -> Skill 匹配准确率 / 工具覆盖率 / RAG 引用命中率
```

## 4. 测试目录建议

```text
tests/
├── test_skill_loader.py
├── test_skill_matcher.py
├── test_sqlite_provider.py
├── test_mcp_tools.py
├── test_rag_retriever.py
├── test_coverage_checker.py
├── test_workflow_smoke.py
├── test_api_diagnose.py
├── test_session_state.py
└── fixtures/
    ├── demo_alerts.json
    ├── expected_skills.json
    └── expected_tool_coverage.json
```

## 5. 测试数据准备

测试前应运行：

```bash
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
uv run python scripts/build_rag_index.py
```

测试数据必须满足：

- 每次 seed 后数据一致。
- 4 个 MVP 故障场景都能复现。
- 至少有一个工具失败或数据缺失案例，用于验证降级报告。
- eval cases 和 demo scenarios 使用相同业务口径。

## 6. Unit Test Cases

### TC-001 Skill loader 能加载 4 个内置 Diagnosis Skill

目标：确认 Skill Center 能扫描并加载内置 Skill。

输入：

```text
app/skills/builtin/*/skill.yaml
```

预期：

- 加载到 4 个 Skill。
- 包含 `airflow_task_failed`、`partition_missing`、`data_volume_drop`、`null_rate_spike`。
- 每个 Skill 都包含 `required_tools` 和 `evidence_requirements`。

断言示例：

```python
assert len(skills) == 4
assert "data_volume_drop" in registry
assert "query_data_volume" in registry["data_volume_drop"].required_tools
```

### TC-002 Skill loader 拒绝缺少 required_tools 的配置

目标：避免无约束 Skill 进入系统。

输入：缺少 `required_tools` 的 `skill.yaml`。

预期：

- 抛出配置校验错误。
- 错误信息包含 skill name 和缺失字段。

### TC-003 Skill matcher 匹配任务失败

输入：

```text
DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。
```

预期：

- selected skill 为 `airflow_task_failed`。
- confidence >= 0.75。
- reason 中包含任务失败或 DAG 失败。

### TC-004 Skill matcher 匹配分区缺失

输入：

```text
dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。
```

预期：

- selected skill 为 `partition_missing`。
- alert_context 中包含 `table_name=dws_sales_daily`。

### TC-005 Skill matcher 匹配数据量突降

输入：

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

预期：

- selected skill 为 `data_volume_drop`。
- alert_context 中包含 `change_ratio=-0.92` 或等价表达。

### TC-006 Skill matcher 匹配字段空值率异常

输入：

```text
ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。
```

预期：

- selected skill 为 `null_rate_spike`。
- alert_context 中包含 `table_name=ads_user_profile` 和 `field_name=user_id`。

### TC-007 低置信度输入触发澄清

输入：

```text
今天销售报表不太对，帮我看看。
```

预期：

- status 为 `needs_clarification`。
- 返回 candidate_diagnosis_skills。
- clarification_question 要求补充表名或异常类型。

### TC-008 CoverageChecker 发现缺失工具

输入：

```json
{
  "required_tools": ["query_data_volume", "query_task_runs", "query_table_partitions", "query_lineage"],
  "called_tools": ["query_data_volume", "query_task_runs", "query_table_partitions"]
}
```

预期：

- missing_tools 包含 `query_lineage`。
- required_tools_coverage 为 0.75。
- confidence_limit 不应为 high。

### TC-009 CoverageChecker 发现缺失证据

输入：工具都调用成功，但 evidence 中没有 downstream_impact。

预期：

- missing_evidence 包含 `downstream_impact`。
- 报告允许生成，但必须包含证据不足说明。

## 7. SQLite Provider Test Cases

### TC-010 query_task_runs 查询失败任务

输入：

```json
{
  "dag_id": "dwd_order_detail_daily",
  "date": "2026-05-14"
}
```

预期：

- 返回 status = `failed`。
- error_message 不为空。
- produces_table = `dwd_order_detail`。

### TC-011 query_table_partitions 查询缺失分区

输入：

```json
{
  "table_name": "dws_sales_daily",
  "date": "2026-05-14"
}
```

预期：

- 返回 partition status = `missing` 或异常状态。
- row_count 为空或显著异常。

### TC-012 query_data_volume 查询 7 天趋势

输入：

```json
{
  "table_name": "dws_sales_daily",
  "start_date": "2026-05-08",
  "end_date": "2026-05-14"
}
```

预期：

- 返回 7 条数据。
- 最后一天 row_count 明显低于前一天。
- change_ratio 接近 -0.92。

### TC-013 query_null_rate 查询字段空值率

输入：

```json
{
  "table_name": "ads_user_profile",
  "field_name": "user_id",
  "start_date": "2026-05-08",
  "end_date": "2026-05-14"
}
```

预期：

- 返回历史空值率。
- 最后一天 actual_value 明显超过 threshold。
- status = `failed` 或 `warning`。

### TC-014 query_lineage 查询下游影响

输入：

```json
{
  "table_name": "dws_sales_daily",
  "direction": "downstream",
  "depth": 3
}
```

预期：

- 返回 `ads_sales_report`。
- 如果 seed 中包含 `ads_revenue_dashboard`，也应返回。

## 8. RAG Test Cases

### TC-015 数据量突降能召回对应 Runbook

查询：

```text
dws_sales_daily 数据量下降 92% 怎么排查
```

过滤条件：

```json
{
  "skill_name": "data_volume_drop"
}
```

预期：

- top 3 中包含 `runbooks/data_volume_drop.md`。
- 返回 source_file、chunk_id、score。

### TC-016 字段空值率异常能召回质量规则文档

查询：

```text
user_id 空值率突然升高
```

预期：

- 返回 `runbooks/null_rate_spike.md` 或 `quality_rules/null_rate_check.md`。
- 返回结果包含字段质量或空值率排查说明。

### TC-017 无相关文档时返回空结果并降级

查询：

```text
一个完全不存在的指标异常场景
```

预期：

- retrieved_docs 可以为空。
- workflow 不应崩溃。
- final_report 应说明未检索到足够知识依据。

## 9. API Test Cases

### TC-018 POST /api/diagnose 端到端成功

输入：数据量突降告警。

预期：

- HTTP 200。
- status = `completed`。
- selected_diagnosis_skill.name = `data_volume_drop`。
- final_report 不为空。
- coverage_result 存在。

### TC-019 POST /api/diagnose 返回澄清

输入：

```text
今天数据不太对。
```

预期：

- HTTP 422 或 code 422。
- status = `needs_clarification`。
- 返回 clarification_question。

### TC-020 GET /api/skills 返回 4 个 Skill

预期：

- HTTP 200。
- skills 数量 >= 4。
- 包含 `data_volume_drop`。

### TC-021 GET /api/incidents/{incident_id} 返回事故详情

前置：完成一次诊断。

预期：

- 返回 raw_alert。
- 返回 selected_diagnosis_skill。
- 返回 final_report。

### TC-022 POST /api/chat 支持多轮追问

前置：完成一次 `data_volume_drop` 诊断。

输入：

```text
它影响哪些下游报表？
```

预期：

- answer 中包含下游表。
- used_state 中包含 current_table。
- references 中包含 `query_lineage`。

## 10. Workflow Smoke Test Cases

### TC-023 Airflow 任务失败端到端

预期链路：

```text
alert -> airflow_task_failed -> query_task_runs -> query_lineage -> report
```

验收：

- 报告包含失败任务、错误摘要、下游影响。

### TC-024 分区缺失端到端

预期链路：

```text
alert -> partition_missing -> query_table_partitions -> query_task_runs -> query_lineage -> report
```

验收：

- 报告能判断当前表或上游依赖问题。

### TC-025 数据量突降端到端

预期链路：

```text
alert -> data_volume_drop -> query_data_volume -> query_table_partitions -> query_task_runs -> query_lineage -> report
```

验收：

- 报告包含 7 天趋势、下降比例、影响范围。

### TC-026 空值率异常端到端

预期链路：

```text
alert -> null_rate_spike -> query_null_rate -> query_task_runs -> query_lineage -> report
```

验收：

- 报告包含字段名、空值率变化、下游影响。

## 11. Eval Cases

### 11.1 Skill 匹配准确率

数据集：`eval/datasets/skill_match_cases.jsonl`

每行格式：

```json
{"input":"dws_sales_daily 今日数据量较昨日下降 92%","expected_skill":"data_volume_drop"}
```

指标：

```text
accuracy = correct_skill_matches / total_cases
```

MVP 目标：>= 85%。

### 11.2 工具覆盖率

数据集：`eval/datasets/tool_coverage_cases.jsonl`

指标：

```text
tool_coverage = called_required_tools / all_required_tools
```

MVP 目标：>= 90%。

### 11.3 RAG 引用命中率

数据集：`eval/datasets/rag_cases.jsonl`

指标：

```text
hit_rate = cases_where_expected_doc_in_top_k / total_cases
```

MVP 目标：>= 80%。

### 11.4 报告证据完整率

检查最终报告是否包含：

- 工具调用证据。
- RAG 引用来源。
- 影响范围。
- 证据不足说明。

MVP 目标：>= 80%。

## 12. 面试讲解口径

可以这样解释测试设计：

```text
我没有只测试 API 能不能返回 200，而是围绕 Agent 最容易出问题的地方设计测试：Skill 是否路由正确、RAG 是否召回对应 Runbook、MCP Tool 是否真的查到了模拟数据、CoverageChecker 是否能发现工具漏查、最终报告是否有证据来源。这样能证明项目不是一个纯 Prompt Demo。
```

最值得主动讲的测试：

- 低置信度触发澄清。
- 缺少 `query_lineage` 时 CoverageChecker 限制报告置信度。
- 数据量突降端到端 smoke test。
- 多轮追问使用 Session State。
