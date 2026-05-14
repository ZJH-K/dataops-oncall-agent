# 06 Database Schema - DataOps OnCall Agent

版本：v0.1
日期：2026-05-14
关联文档：01-product-requirements.md、04-technical-design.md、05-api-spec.md

## 1. 设计目标

本文档定义 DataOps OnCall Agent 的 SQLite 数据库设计。数据库服务于两个目标：

1. 模拟真实数据平台中的任务、表、分区、质量检查和血缘数据。
2. 保存 Agent 诊断过程中的 session、incident、工具调用和最终报告。

本项目使用 SQLite 是为了保证本地演示可复现、测试简单、部署成本低。真实生产环境中，可以把底层 provider 替换为 Airflow API、Hive Metastore、DataHub、Great Expectations、Prometheus 或内部数据质量平台。

## 2. 数据库分层

```text
demo.db
├── 数据平台模拟层
│   ├── dags
│   ├── task_runs
│   ├── data_tables
│   ├── table_partitions
│   ├── data_volume_stats
│   ├── quality_checks
│   └── lineage_edges
├── Agent 运行记录层
│   ├── sessions
│   ├── incidents
│   ├── diagnosis_runs
│   ├── tool_call_logs
│   ├── retrieved_documents
│   └── chat_messages
└── 评估与演示层
    ├── demo_scenarios
    └── eval_cases
```

## 3. 命名约定

- 主键统一使用 `id`，业务 ID 使用 `*_id`。
- 时间字段统一使用 ISO 8601 字符串。
- 日期字段使用 `YYYY-MM-DD`。
- JSON 数据使用 `TEXT` 存储，应用层用 Pydantic 解析。
- 表名避免使用 SQL 保留字，例如使用 `data_tables` 而不是 `tables`。

## 4. 数据平台模拟层

### 4.1 dags

用于模拟 Airflow DAG 或数据调度任务定义。

```sql
CREATE TABLE IF NOT EXISTS dags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dag_id TEXT NOT NULL UNIQUE,
    dag_name TEXT NOT NULL,
    owner TEXT,
    schedule_cron TEXT,
    description TEXT,
    produces_table TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dags_produces_table ON dags(produces_table);
```

字段说明：

| 字段 | 说明 |
|------|------|
| dag_id | 任务唯一标识，例如 `dwd_order_detail_daily` |
| dag_name | 展示名称 |
| owner | 负责人 |
| schedule_cron | 调度周期 |
| produces_table | 该任务主要产出的表 |
| is_active | 是否启用 |

示例数据：

```sql
INSERT INTO dags (dag_id, dag_name, owner, schedule_cron, description, produces_table, created_at, updated_at)
VALUES
('ods_orders_sync_daily', 'ODS Orders Sync Daily', 'data_platform', '0 1 * * *', '同步订单原始数据', 'ods_orders', '2026-05-14T00:00:00+08:00', '2026-05-14T00:00:00+08:00'),
('dwd_order_detail_daily', 'DWD Order Detail Daily', 'data_dev', '0 2 * * *', '加工订单明细表', 'dwd_order_detail', '2026-05-14T00:00:00+08:00', '2026-05-14T00:00:00+08:00'),
('dws_sales_daily_job', 'DWS Sales Daily Job', 'data_dev', '0 3 * * *', '生成每日销售汇总表', 'dws_sales_daily', '2026-05-14T00:00:00+08:00', '2026-05-14T00:00:00+08:00');
```

### 4.2 task_runs

用于模拟任务运行实例。

```sql
CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    dag_id TEXT NOT NULL,
    task_name TEXT,
    biz_date TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    duration_seconds INTEGER,
    error_type TEXT,
    error_message TEXT,
    log_excerpt TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (dag_id) REFERENCES dags(dag_id)
);

CREATE INDEX IF NOT EXISTS idx_task_runs_dag_date ON task_runs(dag_id, biz_date);
CREATE INDEX IF NOT EXISTS idx_task_runs_status ON task_runs(status);
```

状态枚举：

```text
success
failed
running
skipped
upstream_failed
```

MCP Tool 对应：`query_task_runs`

### 4.3 data_tables

用于模拟数据表元数据。

```sql
CREATE TABLE IF NOT EXISTS data_tables (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL UNIQUE,
    layer TEXT NOT NULL,
    owner TEXT,
    description TEXT,
    primary_biz_date_column TEXT NOT NULL DEFAULT 'dt',
    importance_level TEXT NOT NULL DEFAULT 'normal',
    update_frequency TEXT NOT NULL DEFAULT 'daily',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_tables_layer ON data_tables(layer);
CREATE INDEX IF NOT EXISTS idx_data_tables_importance ON data_tables(importance_level);
```

layer 枚举：

```text
ODS
DWD
DWS
ADS
```

示例表：

| table_name | layer | 说明 |
|------------|-------|------|
| ods_orders | ODS | 原始订单表 |
| dwd_order_detail | DWD | 订单明细表 |
| dws_sales_daily | DWS | 每日销售汇总表 |
| ads_sales_report | ADS | 销售日报报表 |
| ads_user_profile | ADS | 用户画像表 |

### 4.4 table_partitions

用于模拟每日分区产出情况。

```sql
CREATE TABLE IF NOT EXISTS table_partitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    partition_date TEXT NOT NULL,
    partition_name TEXT NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER,
    file_size_mb REAL,
    created_time TEXT,
    updated_time TEXT,
    error_message TEXT,
    UNIQUE(table_name, partition_date),
    FOREIGN KEY (table_name) REFERENCES data_tables(table_name)
);

CREATE INDEX IF NOT EXISTS idx_table_partitions_table_date ON table_partitions(table_name, partition_date);
CREATE INDEX IF NOT EXISTS idx_table_partitions_status ON table_partitions(status);
```

status 枚举：

```text
ready
missing
delayed
failed
```

MCP Tool 对应：`query_table_partitions`

### 4.5 data_volume_stats

用于模拟表每日行数趋势，支持数据量突降诊断。

```sql
CREATE TABLE IF NOT EXISTS data_volume_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    stat_date TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    previous_day_row_count INTEGER,
    seven_day_avg_row_count REAL,
    change_ratio REAL,
    anomaly_flag INTEGER NOT NULL DEFAULT 0,
    anomaly_type TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(table_name, stat_date),
    FOREIGN KEY (table_name) REFERENCES data_tables(table_name)
);

CREATE INDEX IF NOT EXISTS idx_data_volume_table_date ON data_volume_stats(table_name, stat_date);
CREATE INDEX IF NOT EXISTS idx_data_volume_anomaly ON data_volume_stats(anomaly_flag);
```

字段说明：

| 字段 | 说明 |
|------|------|
| row_count | 当天行数 |
| previous_day_row_count | 昨日行数 |
| seven_day_avg_row_count | 近 7 天均值 |
| change_ratio | 相比昨日变化比例，例如 -0.92 |
| anomaly_flag | 是否异常 |
| anomaly_type | `drop`、`spike` 等 |

MCP Tool 对应：`query_data_volume`

### 4.6 quality_checks

用于模拟数据质量检查结果，例如空值率、唯一性、范围检查。

```sql
CREATE TABLE IF NOT EXISTS quality_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id TEXT NOT NULL UNIQUE,
    table_name TEXT NOT NULL,
    field_name TEXT,
    check_type TEXT NOT NULL,
    biz_date TEXT NOT NULL,
    status TEXT NOT NULL,
    actual_value REAL,
    expected_value REAL,
    threshold REAL,
    severity TEXT NOT NULL DEFAULT 'P3',
    message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (table_name) REFERENCES data_tables(table_name)
);

CREATE INDEX IF NOT EXISTS idx_quality_checks_table_date ON quality_checks(table_name, biz_date);
CREATE INDEX IF NOT EXISTS idx_quality_checks_type ON quality_checks(check_type);
CREATE INDEX IF NOT EXISTS idx_quality_checks_status ON quality_checks(status);
```

check_type 示例：

```text
null_rate
unique_rate
row_count_range
enum_value
freshness
```

MCP Tool 对应：`query_null_rate`

### 4.7 lineage_edges

用于模拟表血缘关系。

```sql
CREATE TABLE IF NOT EXISTS lineage_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upstream_table TEXT NOT NULL,
    downstream_table TEXT NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'table_to_table',
    transform_desc TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(upstream_table, downstream_table),
    FOREIGN KEY (upstream_table) REFERENCES data_tables(table_name),
    FOREIGN KEY (downstream_table) REFERENCES data_tables(table_name)
);

CREATE INDEX IF NOT EXISTS idx_lineage_upstream ON lineage_edges(upstream_table);
CREATE INDEX IF NOT EXISTS idx_lineage_downstream ON lineage_edges(downstream_table);
```

示例血缘：

```text
ods_orders -> dwd_order_detail -> dws_sales_daily -> ads_sales_report
```

MCP Tool 对应：`query_lineage`

## 5. Agent 运行记录层

### 5.1 sessions

用于保存多轮对话和当前 incident 上下文。

```sql
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,
    current_incident_id TEXT,
    current_table TEXT,
    current_task TEXT,
    current_field TEXT,
    selected_diagnosis_skill TEXT,
    state_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_current_incident ON sessions(current_incident_id);
```

state_json 示例：

```json
{
  "current_table": "dws_sales_daily",
  "selected_diagnosis_skill": "data_volume_drop",
  "evidence_summary": {
    "row_count_drop": "92%",
    "downstream_tables": ["ads_sales_report"]
  }
}
```

### 5.2 incidents

用于保存一次数据事故或诊断事件。

```sql
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    raw_alert TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'P3',
    selected_diagnosis_skill TEXT,
    alert_context_json TEXT,
    coverage_result_json TEXT,
    final_report TEXT,
    confidence_limit TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_incidents_session ON incidents(session_id);
CREATE INDEX IF NOT EXISTS idx_incidents_skill ON incidents(selected_diagnosis_skill);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_created_at ON incidents(created_at);
```

status 枚举：

```text
created
running
needs_clarification
completed
failed
```

severity 枚举：

```text
P0
P1
P2
P3
```

### 5.3 diagnosis_runs

用于记录 LangGraph 每次执行过程的整体状态。

```sql
CREATE TABLE IF NOT EXISTS diagnosis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL UNIQUE,
    incident_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER,
    graph_state_json TEXT,
    error_message TEXT,
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_diagnosis_runs_incident ON diagnosis_runs(incident_id);
CREATE INDEX IF NOT EXISTS idx_diagnosis_runs_status ON diagnosis_runs(status);
```

用途：

- 调试 LangGraph 节点状态。
- 分析诊断失败原因。
- 支持 eval 统计。

### 5.4 tool_call_logs

用于保存 MCP Tool 调用过程。

```sql
CREATE TABLE IF NOT EXISTS tool_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_call_id TEXT NOT NULL UNIQUE,
    run_id TEXT,
    incident_id TEXT,
    session_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    status TEXT NOT NULL,
    result_json TEXT,
    result_summary TEXT,
    error_message TEXT,
    latency_ms INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES diagnosis_runs(run_id),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_tool_call_logs_incident ON tool_call_logs(incident_id);
CREATE INDEX IF NOT EXISTS idx_tool_call_logs_tool_name ON tool_call_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_call_logs_status ON tool_call_logs(status);
```

status 枚举：

```text
started
success
failed
skipped
```

### 5.5 retrieved_documents

用于保存每次诊断 RAG 召回的文档片段。

```sql
CREATE TABLE IF NOT EXISTS retrieved_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    retrieval_id TEXT NOT NULL UNIQUE,
    run_id TEXT,
    incident_id TEXT,
    session_id TEXT NOT NULL,
    query_text TEXT NOT NULL,
    source_file TEXT NOT NULL,
    doc_type TEXT,
    section_title TEXT,
    chunk_id TEXT,
    score REAL,
    content_summary TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES diagnosis_runs(run_id),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_retrieved_documents_incident ON retrieved_documents(incident_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_documents_source ON retrieved_documents(source_file);
```

用途：

- 报告引用来源。
- 分析 RAG 召回是否正确。
- 支持 eval 指标。

### 5.6 chat_messages

用于保存诊断后的多轮追问。

```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL,
    incident_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    references_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_incident ON chat_messages(incident_id);
```

role 枚举：

```text
user
assistant
system
tool
```

## 6. 评估与演示层

### 6.1 demo_scenarios

用于保存固定演示案例。

```sql
CREATE TABLE IF NOT EXISTS demo_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    alert TEXT NOT NULL,
    expected_skill TEXT NOT NULL,
    expected_root_cause TEXT,
    expected_tools_json TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_demo_scenarios_skill ON demo_scenarios(expected_skill);
```

MVP 四个场景：

| scenario_id | expected_skill |
|-------------|----------------|
| case_001_airflow_task_failed | airflow_task_failed |
| case_002_partition_missing | partition_missing |
| case_003_data_volume_drop | data_volume_drop |
| case_004_null_rate_spike | null_rate_spike |

### 6.2 eval_cases

用于保存 eval 数据集。

```sql
CREATE TABLE IF NOT EXISTS eval_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL UNIQUE,
    dataset_name TEXT NOT NULL,
    input_text TEXT NOT NULL,
    expected_skill TEXT,
    expected_tools_json TEXT,
    expected_entities_json TEXT,
    expected_report_keywords_json TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eval_cases_dataset ON eval_cases(dataset_name);
```

用途：

- 评估 Skill 匹配准确率。
- 评估工具覆盖率。
- 评估报告是否包含关键证据。

## 7. MVP 场景数据设计

### 7.1 case_001_airflow_task_failed

告警：

```text
DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。
```

数据设置：

- `dwd_order_detail_daily` 在 `2026-05-14` 状态为 `failed`。
- 错误信息为 `SQL column not found: payment_status`。
- 产出表为 `dwd_order_detail`。
- 下游影响 `dws_sales_daily` 和 `ads_sales_report`。

期望工具：

```json
["query_task_runs", "query_lineage"]
```

### 7.2 case_002_partition_missing

告警：

```text
dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。
```

数据设置：

- `dws_sales_daily` 在 `2026-05-14` 分区状态为 `missing`。
- 上游 `dwd_order_detail` 分区存在但行数异常低。
- 相关任务 `dws_sales_daily_job` 状态为 `upstream_failed`。

期望工具：

```json
["query_table_partitions", "query_task_runs", "query_lineage"]
```

### 7.3 case_003_data_volume_drop

告警：

```text
dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。
```

数据设置：

- `dws_sales_daily` 过去 6 天行数约 10000。
- `2026-05-14` 行数为 800。
- `change_ratio = -0.92`。
- 上游 `payment_orders_sync_daily` 失败，导致支付订单缺失。
- 下游影响 `ads_sales_report` 和 `ads_revenue_dashboard`。

期望工具：

```json
["query_data_volume", "query_task_runs", "query_table_partitions", "query_lineage"]
```

### 7.4 case_004_null_rate_spike

告警：

```text
ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。
```

数据设置：

- `ads_user_profile.user_id` 平时空值率约 0.5%。
- `2026-05-14` 空值率为 35%。
- 上游 `dwd_user_identity` 当天任务成功，但字段映射规则异常。
- 下游影响用户画像看板。

期望工具：

```json
["query_null_rate", "query_task_runs", "query_lineage"]
```

## 8. 查询示例

### 8.1 查询任务运行状态

```sql
SELECT
    tr.run_id,
    tr.dag_id,
    tr.biz_date,
    tr.status,
    tr.error_type,
    tr.error_message,
    d.produces_table
FROM task_runs tr
JOIN dags d ON tr.dag_id = d.dag_id
WHERE tr.dag_id = 'dwd_order_detail_daily'
  AND tr.biz_date = '2026-05-14';
```

### 8.2 查询表分区

```sql
SELECT
    table_name,
    partition_date,
    status,
    row_count,
    error_message
FROM table_partitions
WHERE table_name = 'dws_sales_daily'
  AND partition_date = '2026-05-14';
```

### 8.3 查询数据量趋势

```sql
SELECT
    stat_date,
    row_count,
    previous_day_row_count,
    change_ratio,
    anomaly_flag,
    anomaly_type
FROM data_volume_stats
WHERE table_name = 'dws_sales_daily'
  AND stat_date BETWEEN '2026-05-08' AND '2026-05-14'
ORDER BY stat_date;
```

### 8.4 查询空值率

```sql
SELECT
    table_name,
    field_name,
    biz_date,
    actual_value AS null_rate,
    threshold,
    status,
    severity,
    message
FROM quality_checks
WHERE table_name = 'ads_user_profile'
  AND field_name = 'user_id'
  AND check_type = 'null_rate'
ORDER BY biz_date;
```

### 8.5 查询下游血缘

```sql
WITH RECURSIVE downstream(table_name, depth) AS (
    SELECT downstream_table, 1
    FROM lineage_edges
    WHERE upstream_table = 'dws_sales_daily'

    UNION ALL

    SELECT le.downstream_table, d.depth + 1
    FROM lineage_edges le
    JOIN downstream d ON le.upstream_table = d.table_name
    WHERE d.depth < 3
)
SELECT table_name, depth
FROM downstream;
```

## 9. seed 脚本设计

建议提供三个脚本：

```text
scripts/init_db.py        创建 schema
scripts/seed_demo_data.py 写入固定演示数据
scripts/reset_demo_data.py 删除并重建 demo.db
```

执行顺序：

```bash
uv run python scripts/reset_demo_data.py
uv run python scripts/seed_demo_data.py
```

seed 数据需要保证：

- 每次运行结果一致。
- 四个 MVP 场景都能复现。
- 所有期望工具都能查到数据。
- 至少包含一个工具查不到数据的降级案例。

## 10. 数据库和 MCP Tool 映射

| MCP Tool | 主要查询表 | 说明 |
|----------|------------|------|
| query_task_runs | dags, task_runs | 查询任务状态和失败原因 |
| query_table_partitions | data_tables, table_partitions | 查询分区是否产出 |
| query_data_volume | data_volume_stats | 查询行数趋势和异常比例 |
| query_null_rate | quality_checks | 查询字段空值率 |
| query_lineage | lineage_edges, data_tables | 查询上下游影响 |
| create_incident_report | incidents, diagnosis_runs | 保存报告和诊断状态 |

## 11. 数据库和 API 映射

| API | 读写表 |
|-----|--------|
| POST /api/diagnose | sessions, incidents, diagnosis_runs, tool_call_logs, retrieved_documents |
| POST /api/diagnose/stream | sessions, incidents, diagnosis_runs, tool_call_logs, retrieved_documents |
| POST /api/chat | sessions, chat_messages, incidents |
| GET /api/skills | 文件系统 Skill registry，不依赖 DB |
| GET /api/incidents | incidents |
| GET /api/incidents/{incident_id} | incidents, retrieved_documents |
| GET /api/incidents/{incident_id}/tool-calls | tool_call_logs |
| POST /api/tools/{tool_name}/invoke | 数据平台模拟层 + tool_call_logs |
| POST /api/rag/search | retrieved_documents 可选写入 |

## 12. 约束和风险

### 12.1 SQLite JSON 查询能力有限

MVP 用 TEXT 保存 JSON，复杂筛选在应用层处理。后续如果需要更强查询能力，可以迁移到 PostgreSQL JSONB。

### 12.2 模拟数据不能伪装成真实生产

面试时需要明确说明：当前使用 SQLite 模拟数据平台，重点验证 Agent 诊断流程。真实环境下替换 provider 即可。

### 12.3 表结构不要过度复杂

本项目不是数仓系统本身，数据库只需要支持诊断场景，不需要模拟完整企业数据平台。

## 13. 后续扩展

可扩展表：

- `metric_stats`：支持指标环比异常。
- `sql_errors`：支持 SQL 执行失败诊断。
- `deploy_events`：支持发布后数据异常诊断。
- `owners`：支持负责人和通知链路。
- `incident_actions`：支持人工确认后的修复动作记录。

## 14. 面试讲解口径

可以这样解释数据库设计：

```text
我把数据库分成两类：一类模拟数据平台元数据，包括任务运行、表分区、数据量、质量检查和血缘；另一类记录 Agent 诊断过程，包括 session、incident、工具调用、RAG 引用和最终报告。这样既能稳定复现四类 DataOps 故障，也能把 Agent 的诊断过程完整沉淀下来，方便调试、评估和面试演示。
```

重点强调：

- SQLite 是演示和测试数据源，不是生产承诺。
- MCP Tool 隔离了底层数据源，后续可以替换真实系统。
- tool_call_logs 和 retrieved_documents 是证据链的关键。
- sessions 解决多轮追问中的上下文指代问题。
