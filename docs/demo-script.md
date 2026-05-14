# Demo Script - DataOps OnCall Agent

版本：v1.0
日期：2026-05-14

## 1. 演示目标

用 3 到 5 分钟证明这个项目不是普通 RAG Chatbot，也不是为了堆概念的 Multi-Agent Demo，而是一个可运行、可观察、可评估的 DataOps single-agent 诊断工作流。

核心展示点：

- Diagnosis Skill 匹配过程可见。
- DeepSeek 在告警解析、Skill 路由、规划和摘要中的受控参与可见。
- RAG Runbook 引用可见。
- 阿里云 text-embedding-v4 hybrid retrieval 可见。
- MCP Tool 调用证据可见。
- CoverageChecker 结果可见。
- 最终报告引用工具证据或 RAG 来源。
- Session State 支持多轮追问。

## 2. 演示前准备

```bash
uv sync
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
uv run python scripts/build_rag_index.py --embedding-provider aliyun
uv run pytest tests -q
```

启动服务：

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 9900
```

打开：

```text
http://localhost:9900
```

健康检查：

```bash
curl http://localhost:9900/api/health
```

## 3. 推荐演示案例

使用页面默认的“数据量突降”案例：

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

## 4. 演示步骤和讲解词

### Step 1：展示 4 个 demo alerts

讲法：

```text
这个 MVP 先聚焦 4 类 DataOps 故障：任务失败、分区缺失、数据量突降、字段空值率异常。范围不大，但每个场景都能端到端跑通。
```

### Step 2：点击 Start Diagnosis

讲法：

```text
系统不是直接让模型写答案，而是先进入结构化诊断工作流。
当前版本也不是 Multi-Agent，而是 single-agent workflow：一个共享 DiagnosisState 在 LangGraph 节点之间流转。DeepSeek 参与关键决策，但工具执行和 CoverageChecker 仍由代码约束。
```

### Step 3：展示 Diagnosis Skill

看到 `data_volume_drop` 后讲：

```text
Diagnosis Skill 是诊断策略，不是工具。它定义这个场景必须查哪些工具、需要哪些证据，以及报告输出应该受什么约束。
```

### Step 4：展示 RAG references

重点指向：

```text
docs/runbooks/data_volume_drop.md
docs/tables/dws_sales_daily.md
```

讲法：

```text
RAG 在这里不是泛泛问答，而是给诊断流程提供 Runbook、表说明和历史事故依据。报告里必须展示 source_file 和 section_title。
如果启用了阿里云 embedding，这里是 keyword/metadata + text-embedding-v4 的 hybrid retrieval。
```

### Step 5：展示 Tool timeline

重点工具：

```text
query_data_volume
query_task_runs
query_table_partitions
query_lineage
```

讲法：

```text
MCP Tool 负责查事实。这里 SQLite 只是模拟数据平台，工具 schema 和 provider 边界是可替换的，后续可以接 Airflow、DataHub 或质量平台。
```

### Step 6：展示 CoverageChecker

讲法：

```text
CoverageChecker 会对照 Diagnosis Skill 的 required_tools 和 evidence_requirements，防止工具没查全时过早输出确定根因。
```

### Step 7：展示最终报告

重点展示：

- 告警摘要。
- RAG 引用来源。
- 工具调用证据。
- CoverageChecker。
- 根因判断。
- 影响范围。
- 证据不足说明。

讲法：

```text
最终报告不是纯 Prompt 生成，它绑定了工具结果和 RAG 来源。如果证据不足，报告会明确限制结论。
```

### Step 8：多轮追问

输入：

```text
它影响哪些下游报表？
```

讲法：

```text
这里的“它”不是靠聊天历史猜，而是从 Session State 中读取当前 incident、当前表和 query_lineage 证据。
```

## 5. 30 秒收尾

```text
这个项目的核心不是把 Agent 包装成聊天，而是把 DataOps 故障诊断拆成可执行、可观察、可评估的工作流。Diagnosis Skill 负责策略，RAG 负责知识，MCP Tool 负责证据，LangGraph 负责编排，CoverageChecker 负责约束，Session State 负责多轮上下文。
当前版本准确说是 single-agent workflow，不是 Multi-Agent；后续可以拆成 Triage、Evidence、Knowledge、Reporter、Reviewer 多个 Agent。
```

## 6. 常见演示风险

### 服务没启动

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 9900
```

### RAG index 缺失

```bash
uv run python scripts/build_rag_index.py
```

### 数据被上次演示污染

```bash
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
```

### 想证明不是纯 Demo

```bash
uv run pytest tests -q
uv run python eval/run_eval.py --dataset skill_match_cases
uv run python eval/run_eval.py --dataset rag_cases
uv run python eval/run_eval.py --dataset tool_coverage_cases
```
