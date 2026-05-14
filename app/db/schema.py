import sqlite3


SCHEMA_SQL = """
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

CREATE INDEX IF NOT EXISTS idx_table_partitions_table_date
    ON table_partitions(table_name, partition_date);
CREATE INDEX IF NOT EXISTS idx_table_partitions_status ON table_partitions(status);

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

CREATE INDEX IF NOT EXISTS idx_data_volume_table_date
    ON data_volume_stats(table_name, stat_date);
CREATE INDEX IF NOT EXISTS idx_data_volume_anomaly ON data_volume_stats(anomaly_flag);

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

CREATE INDEX IF NOT EXISTS idx_quality_checks_table_date
    ON quality_checks(table_name, biz_date);
CREATE INDEX IF NOT EXISTS idx_quality_checks_type ON quality_checks(check_type);
CREATE INDEX IF NOT EXISTS idx_quality_checks_status ON quality_checks(status);

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

CREATE INDEX IF NOT EXISTS idx_sessions_current_incident
    ON sessions(current_incident_id);

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

CREATE INDEX IF NOT EXISTS idx_diagnosis_runs_incident
    ON diagnosis_runs(incident_id);
CREATE INDEX IF NOT EXISTS idx_diagnosis_runs_status ON diagnosis_runs(status);

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

CREATE INDEX IF NOT EXISTS idx_tool_call_logs_incident
    ON tool_call_logs(incident_id);
CREATE INDEX IF NOT EXISTS idx_tool_call_logs_tool_name
    ON tool_call_logs(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_call_logs_status ON tool_call_logs(status);

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

CREATE INDEX IF NOT EXISTS idx_retrieved_documents_incident
    ON retrieved_documents(incident_id);
CREATE INDEX IF NOT EXISTS idx_retrieved_documents_source
    ON retrieved_documents(source_file);

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

CREATE INDEX IF NOT EXISTS idx_chat_messages_session
    ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_incident
    ON chat_messages(incident_id);

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

CREATE INDEX IF NOT EXISTS idx_demo_scenarios_skill
    ON demo_scenarios(expected_skill);

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
"""


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)

