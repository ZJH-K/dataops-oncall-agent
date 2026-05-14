# TASKS.md - 实现任务清单

## 1. 如何使用这个文件

这个文件是项目执行清单。不要试图在一个 AI 对话里做完整项目。

每次新开项目对话，推荐流程：

```text
1. 先阅读 AGENTS.md。
2. 再阅读 TASKS.md。
3. 只选择下一个未完成批次。
4. 实现这个批次。
5. 运行验证命令。
6. 更新 TASKS.md 中对应批次的状态和备注。
```

状态说明：

```text
[ ] 未开始
[~] 进行中
[x] 已完成
[!] 阻塞
```

## 2. 批次总览

| 批次 | 目标 | 简历价值 | 状态 |
|------|------|----------|------|
| B0 | 项目脚手架 | 可运行基础 | [x] |
| B1 | SQLite schema + seed 数据 | 可复现演示数据 | [x] |
| B2 | Diagnosis Skill Center | 项目核心差异点 | [x] |
| B3 | MCP Tool server | 工具调用证据 | [x] |
| B4 | RAG 知识检索 | Runbook 和引用来源 | [x] |
| B5 | LangGraph 诊断工作流 | Agent 编排能力 | [x] |
| B6 | FastAPI 接口 | 后端应用层 | [x] |
| B7 | Demo UI | 面试演示 | [x] |
| B8 | 测试和 eval | 证明不是纯 Demo | [x] |
| B9 | README 和面试材料 | 简历可投状态 | [x] |

## 3. B0 - 项目脚手架

目标：创建一个干净的 Python 项目，并能本地启动。

任务：

- [x] 创建 `app/` 项目包结构。
- [x] 创建 `pyproject.toml`。
- [x] 创建 `.env.example`。
- [x] 添加基础 `app/main.py`，实现 `/api/health`。
- [x] 创建空目录：`scripts/`、`mcp_servers/`、`docs/runbooks/`、`docs/tables/`、`docs/postmortems/`、`docs/quality_rules/`、`tests/`、`eval/`、`data/`。
- [x] 添加 README 占位文件。

状态备注：

```text
2026-05-14 已完成 B0。使用 uv 创建本地环境，FastAPI /api/health 返回 {"status":"ok"}。
```

验证命令：

```bash
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 9900
curl http://localhost:9900/api/health
```

完成标准：

```text
/api/health 返回 ok。
项目结构大体符合 docs/04-technical-design.md。
```

## 4. B1 - SQLite Schema 和 Seed 数据

目标：创建可复现的 DataOps 演示数据。

任务：

- [x] 实现 `scripts/init_db.py`。
- [x] 实现 `scripts/reset_demo_data.py`。
- [x] 实现 `scripts/seed_demo_data.py`。
- [x] 根据 `docs/06-database-schema.md` 创建表结构。
- [x] 写入核心表：`dags`、`task_runs`、`data_tables`、`table_partitions`、`data_volume_stats`、`quality_checks`、`lineage_edges`。
- [x] 写入 4 个 demo scenarios。
- [x] 添加 SQLite 访问 helper/repository。

状态备注：

```text
2026-05-14 已完成 B1。SQLite schema 已创建，reset/seed 脚本可复现写入 4 个 MVP 场景。
data_volume_drop 场景中 dws_sales_daily 在 2026-05-14 从 10000 行降至 800 行，change_ratio = -0.92。
```

验证命令：

```bash
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
```

手动 SQL 检查：

```sql
SELECT * FROM data_volume_stats WHERE table_name='dws_sales_daily';
SELECT * FROM task_runs WHERE status='failed';
SELECT * FROM lineage_edges;
```

完成标准：

```text
4 个 MVP 场景都有对应数据。
data_volume_drop 场景能看到 92% 数据量下降。
```

## 5. B2 - Diagnosis Skill Center

目标：实现项目特有的 Diagnosis Skill 抽象。

任务：

- [x] 创建 `app/skills/models.py`。
- [x] 创建 `app/skills/loader.py`。
- [x] 创建 `app/skills/matcher.py`。
- [x] 创建 4 个内置 Skill 目录：
  - [x] `airflow_task_failed`
  - [x] `partition_missing`
  - [x] `data_volume_drop`
  - [x] `null_rate_spike`
- [x] 为每个 Skill 添加 `skill.yaml`、`runbook.md`、`examples.json`。
- [x] 先实现规则匹配。
- [x] LLM rerank 后续可选，本批次按 MVP 规则匹配实现。

状态备注：

```text
2026-05-14 已完成 B2。4 个内置 Diagnosis Skill 可加载，规则 matcher 可匹配 4 条 demo 告警。
模糊告警会返回 needs_clarification，避免低置信度时过早选择 Skill。
```

验证命令：

```bash
uv run pytest tests/test_skill_loader.py -q
uv run pytest tests/test_skill_matcher.py -q
```

完成标准：

```text
4 个 Skill 能成功加载。
4 条清晰 demo 告警能匹配到预期 Skill。
模糊告警能返回 needs_clarification 或低置信度。
```

## 6. B3 - MCP Tool Server

目标：通过本地 MCP Server 暴露 DataOps 查询工具。

任务：

- [x] 实现 SQLite provider interface。
- [x] 实现 `query_task_runs`。
- [x] 实现 `query_table_partitions`。
- [x] 实现 `query_data_volume`。
- [x] 实现 `query_null_rate`。
- [x] 实现 `query_lineage`。
- [x] 实现 `create_incident_report`。
- [x] 将工具调用写入 `tool_call_logs`。
- [x] 创建 `mcp_servers/dataops_server.py`。

状态备注：

```text
2026-05-14 已完成 B3。SQLiteDataOpsToolProvider 暴露 6 个 DataOps 工具，并为 success/failed 调用写入 tool_call_logs。
mcp_servers/dataops_server.py 提供本地 JSON CLI 工具入口，可列出工具或调用单个工具。
```

验证命令：

```bash
uv run python mcp_servers/dataops_server.py
uv run pytest tests/test_mcp_tools.py -q
```

完成标准：

```text
每个工具都可以独立调用，并返回结构化 JSON。
工具失败会被记录，不会被吞掉。
```

## 7. B4 - RAG 知识检索

目标：能检索 Runbook、表说明、质量规则和历史事故，并返回引用来源。

任务：

- [x] 创建 4 篇 Runbook。
- [x] 创建 `dws_sales_daily` 和 `ads_user_profile` 表说明。
- [x] 创建至少 2 篇 postmortem 文档。
- [x] 实现 `scripts/build_rag_index.py`。
- [x] 实现 `app/rag/retriever.py`。
- [x] 保存 metadata：`source_file`、`doc_type`、`section_title`、`skill_name`、`table_name`、`chunk_id`。
- [x] retriever 返回 top-k 结果和来源信息。

状态备注：

```text
2026-05-14 已完成 B4。已创建 Runbook、表说明、质量规则、事故复盘文档，并构建 data/rag_index.json。
LocalRagRetriever 支持 metadata filter + 关键词检索，data_volume_drop 查询 top 3 可召回 data_volume_drop runbook，null_rate 查询 top 3 可召回空值率相关文档。
```

验证命令：

```bash
uv run python scripts/build_rag_index.py
uv run pytest tests/test_rag_retriever.py -q
```

完成标准：

```text
data_volume_drop 查询能在 top 3 召回 data_volume_drop runbook。
null_rate 查询能在 top 3 召回空值率相关文档。
```

## 8. B5 - LangGraph 诊断工作流

目标：构建核心 Agent 诊断工作流。

任务：

- [x] 实现 `app/workflow/state.py`。
- [x] 实现节点：
  - [x] AlertParser
  - [x] DiagnosisSkillMatcher
  - [x] KnowledgeRetriever
  - [x] Planner
  - [x] ToolExecutor
  - [x] CoverageChecker
  - [x] Reporter
  - [x] IncidentRecorder
- [x] 实现 graph edges 和条件分支。
- [x] 支持 needs_clarification 路径。
- [x] 支持缺失工具/证据路径。
- [x] 保存 state 到 sessions/incidents。

状态备注：

```text
2026-05-14 已完成 B5。使用 LangGraph StateGraph 编排 AlertParser -> DiagnosisSkillMatcher -> KnowledgeRetriever -> Planner -> ToolExecutor -> CoverageChecker -> Reporter -> IncidentRecorder。
data_volume_drop 场景可从告警跑到报告，返回 selected_diagnosis_skill、tool_calls、coverage_result、final_report 和 incident_id。
```

验证命令：

```bash
uv run pytest tests/test_workflow_smoke.py -q
```

完成标准：

```text
data_volume_drop 场景能从告警跑到报告。
Workflow 返回 selected_diagnosis_skill、tool_calls、coverage_result、final_report。
```

## 9. B6 - FastAPI 接口

目标：通过稳定 API 暴露诊断工作流。

任务：

- [x] 实现 `GET /api/health`。
- [x] 实现 `POST /api/diagnose`。
- [x] 实现 `POST /api/diagnose/stream`。
- [x] 实现 `POST /api/chat`。
- [x] 实现 `GET /api/skills`。
- [x] 实现 `GET /api/skills/{skill_name}`。
- [x] 实现 `POST /api/skills/match`。
- [x] 实现 `GET /api/incidents`。
- [x] 实现 `GET /api/incidents/{incident_id}`。
- [x] 实现 `GET /api/incidents/{incident_id}/tool-calls`。
- [ ] 可选：工具和 RAG debug API 留到后续按需实现。

状态备注：

```text
2026-05-14 已完成 B6。新增 app/api 路由、schema 和 service 层，核心 API 可以暴露 Diagnosis Skill、Workflow、RAG 引用、MCP Tool 调用证据、Incident 查询和基于 Session State 的多轮追问。
POST /api/diagnose 可跑通 data_volume_drop，GET /api/incidents/{incident_id}/tool-calls 可查询诊断过程工具调用。
```

验证命令：

```bash
uv run pytest tests/test_api_diagnose.py -q
curl http://localhost:9900/api/health
```

完成标准：

```text
核心 API 符合 docs/05-api-spec.md。
非流式 diagnose 能跑通 data_volume_drop。
```

## 10. B7 - Demo UI

目标：创建一个适合面试演示的简单前端。

任务：

- [x] 创建单页 UI。
- [x] 添加 4 个 demo alert 按钮。
- [x] 展示 Diagnosis Skill 匹配结果。
- [x] 展示 RAG retrieved docs。
- [x] 展示 tool call timeline。
- [x] 展示 CoverageChecker 输出。
- [x] 展示最终 Markdown 报告。
- [x] 添加多轮追问输入框。

状态备注：

```text
2026-05-14 已完成 B7。新增 static/index.html、static/styles.css、static/app.js，并在 FastAPI 根路径 / 挂载诊断工作台。
UI 支持 4 个 demo alert、data_volume_drop 默认演示、Diagnosis Skill / RAG / Tool timeline / CoverageChecker / Markdown report / Session State chat 展示。
```

验证方式：

```text
打开 http://localhost:9900，在 3 分钟内完成 data_volume_drop 演示。
```

完成标准：

```text
UI 能清楚展示完整 pipeline，足够用于面试。
```

## 11. B8 - 测试和 Eval

目标：证明项目不是纯 Demo。

任务：

- [x] 添加 Skill match eval 数据集。
- [x] 添加 RAG eval 数据集。
- [x] 添加 tool coverage eval 数据集。
- [x] 实现 `eval/run_eval.py`。
- [x] 添加 4 个 MVP 场景 smoke tests。
- [x] 添加报告证据检查。

状态备注：

```text
2026-05-14 已完成 B8。新增 eval/datasets/skill_match_cases.jsonl、rag_cases.jsonl、tool_coverage_cases.jsonl 和 eval/run_eval.py。
全量 pytest 34 passed；Skill match accuracy = 1.0，RAG hit rate = 1.0，tool coverage = 1.0。
4 个 MVP 场景均可端到端跑通，报告检查覆盖 RAG 引用、工具调用证据和 CoverageChecker。
```

验证命令：

```bash
uv run pytest tests -q
uv run python eval/run_eval.py --dataset skill_match_cases
uv run python eval/run_eval.py --dataset rag_cases
uv run python eval/run_eval.py --dataset tool_coverage_cases
```

完成标准：

```text
Skill match accuracy >= 85%。
RAG hit rate >= 80%。
Tool coverage >= 90%。
```

## 12. B9 - README 和面试材料

目标：让项目达到简历可投状态。

任务：

- [x] 编写最终 README。
- [x] 添加架构图。
- [x] 添加 setup 命令。
- [x] 添加 demo script。
- [x] 添加 limitations 和诚实边界说明。
- [x] 尽可能添加截图或 GIF。
- [x] 添加简历项目描述。
- [x] 用真实实现记录更新 `docs/09-challenges-and-solutions.md`。
- [x] 用最终项目信息更新 `docs/10-interview-talking-points.md`。

状态备注：

```text
2026-05-14 已完成 B9。README 已更新为最终项目入口，包含架构图、setup 命令、Demo UI 截图、演示脚本、测试/eval 命令、限制说明和简历描述。
新增 docs/demo-script.md，更新 docs/08-deployment.md、docs/09-challenges-and-solutions.md、docs/10-interview-talking-points.md。
最终验证：pytest 34 passed；Skill match accuracy = 1.0，RAG hit rate = 1.0，tool coverage = 1.0。
```

完成标准：

```text
别人能根据 README clone、安装、运行、理解项目。
你能不看稿用 2 分钟讲清楚项目。
```

## 13. 推荐新对话拆分

建议在新项目区按这个节奏开对话：

```text
第 1 次：B0 项目脚手架
第 2 次：B1 SQLite schema 和 seed 数据
第 3 次：B2 Diagnosis Skill Center
第 4 次：B3 MCP Tool server
第 5 次：B4 RAG 文档和 retriever
第 6 次：B5 LangGraph workflow
第 7 次：B6 API endpoints
第 8 次：B7 Demo UI
第 9 次：B8 tests 和 eval
第 10 次：B9 README 和面试打磨
```

不要让一个对话一次性尝试 B0-B9，也不要默认把 B0 和 B1 合并做。

每次新对话只做当前批次。如果当前批次完成后还有时间，也先停下来更新状态，再由用户决定是否继续下一个批次。

## 14. 当前下一步

当前推荐任务：

```text
MVP 项目闭环完成。已完成 DeepSeek 决策辅助、阿里云 text-embedding-v4 hybrid RAG 和 single-agent workflow 定位修正。
```

给项目区新对话的提示词：

```text
请先阅读 AGENTS.md 和 TASKS.md。当前 DataOps OnCall Agent MVP 已完成，并已接入 DeepSeek 决策辅助和阿里云 text-embedding-v4 hybrid RAG。当前版本定位为 single-agent workflow，不是 Multi-Agent。请根据我的新目标选择下一步：Demo UI 展示 LLM 决策节点、截图/GIF 增强、真实 provider 扩展设计、代码 review，或继续扩展测试数据。
```
