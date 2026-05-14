from collections.abc import Sequence
import json
import sqlite3

from app.db.schema import initialize_schema


NOW = "2026-05-14T00:00:00+08:00"
BIZ_DATE = "2026-05-14"


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _insert_many(
    connection: sqlite3.Connection,
    table: str,
    rows: Sequence[dict[str, object]],
) -> None:
    if not rows:
        return

    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(column)

    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    connection.executemany(sql, ([row.get(column) for column in columns] for row in rows))


def clear_demo_data(connection: sqlite3.Connection) -> None:
    tables = [
        "chat_messages",
        "retrieved_documents",
        "tool_call_logs",
        "diagnosis_runs",
        "incidents",
        "sessions",
        "eval_cases",
        "demo_scenarios",
        "lineage_edges",
        "quality_checks",
        "data_volume_stats",
        "table_partitions",
        "task_runs",
        "dags",
        "data_tables",
    ]
    for table in tables:
        connection.execute(f"DELETE FROM {table}")
    connection.execute(
        "DELETE FROM sqlite_sequence WHERE name IN "
        f"({', '.join('?' for _ in tables)})",
        tables,
    )


def seed_demo_data(connection: sqlite3.Connection) -> None:
    initialize_schema(connection)
    clear_demo_data(connection)

    _insert_many(
        connection,
        "data_tables",
        [
            {
                "table_name": "ods_orders",
                "layer": "ODS",
                "owner": "data_platform",
                "description": "Raw order records synced from the source order system.",
                "importance_level": "normal",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "ods_payment_orders",
                "layer": "ODS",
                "owner": "data_platform",
                "description": "Raw payment order records from the payment gateway.",
                "importance_level": "high",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "dwd_order_detail",
                "layer": "DWD",
                "owner": "data_dev",
                "description": "Cleaned order detail table used by sales aggregates.",
                "importance_level": "high",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "dwd_payment_order",
                "layer": "DWD",
                "owner": "data_dev",
                "description": "Cleaned payment order detail table.",
                "importance_level": "high",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "layer": "DWS",
                "owner": "data_dev",
                "description": "Daily sales aggregate table for reports and dashboards.",
                "importance_level": "critical",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "ads_sales_report",
                "layer": "ADS",
                "owner": "analytics",
                "description": "Daily sales report consumed by business users.",
                "importance_level": "critical",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "ads_revenue_dashboard",
                "layer": "ADS",
                "owner": "analytics",
                "description": "Revenue dashboard fed by daily sales aggregates.",
                "importance_level": "critical",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "dwd_user_identity",
                "layer": "DWD",
                "owner": "user_data",
                "description": "User identity mapping table.",
                "importance_level": "high",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "ads_user_profile",
                "layer": "ADS",
                "owner": "user_data",
                "description": "User profile table used by recommendation and CRM scenarios.",
                "importance_level": "high",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "table_name": "ads_user_profile_dashboard",
                "layer": "ADS",
                "owner": "analytics",
                "description": "Dashboard tracking user profile coverage and quality.",
                "importance_level": "normal",
                "created_at": NOW,
                "updated_at": NOW,
            },
        ],
    )

    _insert_many(
        connection,
        "dags",
        [
            {
                "dag_id": "ods_orders_sync_daily",
                "dag_name": "ODS Orders Sync Daily",
                "owner": "data_platform",
                "schedule_cron": "0 1 * * *",
                "description": "Sync raw order data.",
                "produces_table": "ods_orders",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "dag_id": "payment_orders_sync_daily",
                "dag_name": "Payment Orders Sync Daily",
                "owner": "data_platform",
                "schedule_cron": "10 1 * * *",
                "description": "Sync raw payment orders.",
                "produces_table": "ods_payment_orders",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "dag_id": "dwd_order_detail_daily",
                "dag_name": "DWD Order Detail Daily",
                "owner": "data_dev",
                "schedule_cron": "0 2 * * *",
                "description": "Build cleaned order detail table.",
                "produces_table": "dwd_order_detail",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "dag_id": "dwd_payment_order_daily",
                "dag_name": "DWD Payment Order Daily",
                "owner": "data_dev",
                "schedule_cron": "20 2 * * *",
                "description": "Build cleaned payment order table.",
                "produces_table": "dwd_payment_order",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "dag_id": "dws_sales_daily_job",
                "dag_name": "DWS Sales Daily Job",
                "owner": "data_dev",
                "schedule_cron": "0 3 * * *",
                "description": "Build daily sales aggregates.",
                "produces_table": "dws_sales_daily",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "dag_id": "dwd_user_identity_daily",
                "dag_name": "DWD User Identity Daily",
                "owner": "user_data",
                "schedule_cron": "30 1 * * *",
                "description": "Build user identity mappings.",
                "produces_table": "dwd_user_identity",
                "created_at": NOW,
                "updated_at": NOW,
            },
            {
                "dag_id": "ads_user_profile_daily",
                "dag_name": "ADS User Profile Daily",
                "owner": "user_data",
                "schedule_cron": "30 3 * * *",
                "description": "Build user profile output table.",
                "produces_table": "ads_user_profile",
                "created_at": NOW,
                "updated_at": NOW,
            },
        ],
    )

    _insert_many(
        connection,
        "task_runs",
        [
            {
                "run_id": "run_ods_orders_20260514",
                "dag_id": "ods_orders_sync_daily",
                "task_name": "sync_orders",
                "biz_date": BIZ_DATE,
                "status": "success",
                "start_time": "2026-05-14T01:00:00+08:00",
                "end_time": "2026-05-14T01:12:00+08:00",
                "duration_seconds": 720,
                "retry_count": 0,
                "created_at": NOW,
            },
            {
                "run_id": "run_payment_orders_20260514",
                "dag_id": "payment_orders_sync_daily",
                "task_name": "sync_payment_orders",
                "biz_date": BIZ_DATE,
                "status": "failed",
                "start_time": "2026-05-14T01:10:00+08:00",
                "end_time": "2026-05-14T01:18:00+08:00",
                "duration_seconds": 480,
                "error_type": "SourceUnavailable",
                "error_message": "payment gateway export file was not found",
                "log_excerpt": "FileNotFoundError: /exports/payment_orders/dt=2026-05-14",
                "retry_count": 2,
                "created_at": NOW,
            },
            {
                "run_id": "run_dwd_order_detail_20260514",
                "dag_id": "dwd_order_detail_daily",
                "task_name": "build_order_detail",
                "biz_date": BIZ_DATE,
                "status": "failed",
                "start_time": "2026-05-14T02:00:00+08:00",
                "end_time": "2026-05-14T02:05:20+08:00",
                "duration_seconds": 320,
                "error_type": "SqlCompileError",
                "error_message": "SQL column not found: payment_status",
                "log_excerpt": "AnalysisException: cannot resolve column payment_status",
                "retry_count": 1,
                "created_at": NOW,
            },
            {
                "run_id": "run_dwd_payment_order_20260514",
                "dag_id": "dwd_payment_order_daily",
                "task_name": "build_payment_order",
                "biz_date": BIZ_DATE,
                "status": "upstream_failed",
                "start_time": "2026-05-14T02:20:00+08:00",
                "end_time": "2026-05-14T02:20:30+08:00",
                "duration_seconds": 30,
                "error_type": "UpstreamFailed",
                "error_message": "payment_orders_sync_daily failed",
                "log_excerpt": "Skipping because upstream raw payment data is unavailable.",
                "retry_count": 0,
                "created_at": NOW,
            },
            {
                "run_id": "run_dws_sales_daily_20260514",
                "dag_id": "dws_sales_daily_job",
                "task_name": "build_sales_daily",
                "biz_date": BIZ_DATE,
                "status": "upstream_failed",
                "start_time": "2026-05-14T03:00:00+08:00",
                "end_time": "2026-05-14T03:01:00+08:00",
                "duration_seconds": 60,
                "error_type": "UpstreamFailed",
                "error_message": "upstream payment order table is incomplete",
                "log_excerpt": "Detected missing upstream payment partition before aggregation.",
                "retry_count": 0,
                "created_at": NOW,
            },
            {
                "run_id": "run_dwd_user_identity_20260514",
                "dag_id": "dwd_user_identity_daily",
                "task_name": "build_user_identity",
                "biz_date": BIZ_DATE,
                "status": "success",
                "start_time": "2026-05-14T01:30:00+08:00",
                "end_time": "2026-05-14T01:48:00+08:00",
                "duration_seconds": 1080,
                "retry_count": 0,
                "created_at": NOW,
            },
            {
                "run_id": "run_ads_user_profile_20260514",
                "dag_id": "ads_user_profile_daily",
                "task_name": "build_user_profile",
                "biz_date": BIZ_DATE,
                "status": "success",
                "start_time": "2026-05-14T03:30:00+08:00",
                "end_time": "2026-05-14T03:47:00+08:00",
                "duration_seconds": 1020,
                "retry_count": 0,
                "created_at": NOW,
            },
        ],
    )

    _insert_many(
        connection,
        "table_partitions",
        [
            {
                "table_name": "ods_orders",
                "partition_date": BIZ_DATE,
                "partition_name": "dt=2026-05-14",
                "status": "ready",
                "row_count": 12000,
                "file_size_mb": 64.2,
                "created_time": "2026-05-14T01:12:00+08:00",
                "updated_time": "2026-05-14T01:12:00+08:00",
            },
            {
                "table_name": "ods_payment_orders",
                "partition_date": BIZ_DATE,
                "partition_name": "dt=2026-05-14",
                "status": "missing",
                "row_count": 0,
                "file_size_mb": 0,
                "created_time": None,
                "updated_time": None,
                "error_message": "source export file missing",
            },
            {
                "table_name": "dwd_order_detail",
                "partition_date": BIZ_DATE,
                "partition_name": "dt=2026-05-14",
                "status": "ready",
                "row_count": 1200,
                "file_size_mb": 18.5,
                "created_time": "2026-05-14T02:08:00+08:00",
                "updated_time": "2026-05-14T02:08:00+08:00",
                "error_message": "partial output; row count lower than expected",
            },
            {
                "table_name": "dwd_payment_order",
                "partition_date": BIZ_DATE,
                "partition_name": "dt=2026-05-14",
                "status": "missing",
                "row_count": 0,
                "file_size_mb": 0,
                "created_time": None,
                "updated_time": None,
                "error_message": "upstream payment data missing",
            },
            {
                "table_name": "dws_sales_daily",
                "partition_date": BIZ_DATE,
                "partition_name": "dt=2026-05-14",
                "status": "missing",
                "row_count": 0,
                "file_size_mb": 0,
                "created_time": None,
                "updated_time": None,
                "error_message": "scheduled partition not produced",
            },
            {
                "table_name": "ads_user_profile",
                "partition_date": BIZ_DATE,
                "partition_name": "dt=2026-05-14",
                "status": "ready",
                "row_count": 52000,
                "file_size_mb": 88.4,
                "created_time": "2026-05-14T03:47:00+08:00",
                "updated_time": "2026-05-14T03:47:00+08:00",
            },
        ],
    )

    _insert_many(
        connection,
        "data_volume_stats",
        [
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-08",
                "row_count": 10120,
                "previous_day_row_count": 10090,
                "seven_day_avg_row_count": 10030.0,
                "change_ratio": 0.003,
                "anomaly_flag": 0,
                "created_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-09",
                "row_count": 9950,
                "previous_day_row_count": 10120,
                "seven_day_avg_row_count": 10040.0,
                "change_ratio": -0.0168,
                "anomaly_flag": 0,
                "created_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-10",
                "row_count": 10340,
                "previous_day_row_count": 9950,
                "seven_day_avg_row_count": 10080.0,
                "change_ratio": 0.0392,
                "anomaly_flag": 0,
                "created_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-11",
                "row_count": 10080,
                "previous_day_row_count": 10340,
                "seven_day_avg_row_count": 10110.0,
                "change_ratio": -0.0251,
                "anomaly_flag": 0,
                "created_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-12",
                "row_count": 10210,
                "previous_day_row_count": 10080,
                "seven_day_avg_row_count": 10120.0,
                "change_ratio": 0.0129,
                "anomaly_flag": 0,
                "created_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-13",
                "row_count": 10000,
                "previous_day_row_count": 10210,
                "seven_day_avg_row_count": 10110.0,
                "change_ratio": -0.0206,
                "anomaly_flag": 0,
                "created_at": NOW,
            },
            {
                "table_name": "dws_sales_daily",
                "stat_date": "2026-05-14",
                "row_count": 800,
                "previous_day_row_count": 10000,
                "seven_day_avg_row_count": 10116.7,
                "change_ratio": -0.92,
                "anomaly_flag": 1,
                "anomaly_type": "drop",
                "created_at": NOW,
            },
        ],
    )

    quality_rows = []
    normal_rates = [
        ("2026-05-08", 0.004),
        ("2026-05-09", 0.006),
        ("2026-05-10", 0.005),
        ("2026-05-11", 0.004),
        ("2026-05-12", 0.005),
        ("2026-05-13", 0.006),
    ]
    for stat_date, null_rate in normal_rates:
        quality_rows.append(
            {
                "check_id": f"qc_ads_user_profile_user_id_null_rate_{stat_date}",
                "table_name": "ads_user_profile",
                "field_name": "user_id",
                "check_type": "null_rate",
                "biz_date": stat_date,
                "status": "success",
                "actual_value": null_rate,
                "expected_value": 0.005,
                "threshold": 0.02,
                "severity": "P3",
                "message": "user_id null rate is within the expected range",
                "created_at": NOW,
            }
        )
    quality_rows.append(
        {
            "check_id": "qc_ads_user_profile_user_id_null_rate_2026-05-14",
            "table_name": "ads_user_profile",
            "field_name": "user_id",
            "check_type": "null_rate",
            "biz_date": BIZ_DATE,
            "status": "failed",
            "actual_value": 0.35,
            "expected_value": 0.005,
            "threshold": 0.02,
            "severity": "P1",
            "message": "user_id null rate spiked after identity mapping rule change",
            "created_at": NOW,
        }
    )
    _insert_many(connection, "quality_checks", quality_rows)

    _insert_many(
        connection,
        "lineage_edges",
        [
            {
                "upstream_table": "ods_orders",
                "downstream_table": "dwd_order_detail",
                "transform_desc": "Clean raw order records into order detail facts.",
                "created_at": NOW,
            },
            {
                "upstream_table": "ods_payment_orders",
                "downstream_table": "dwd_payment_order",
                "transform_desc": "Clean raw payment order records.",
                "created_at": NOW,
            },
            {
                "upstream_table": "dwd_order_detail",
                "downstream_table": "dws_sales_daily",
                "transform_desc": "Aggregate order details into daily sales metrics.",
                "created_at": NOW,
            },
            {
                "upstream_table": "dwd_payment_order",
                "downstream_table": "dws_sales_daily",
                "transform_desc": "Join payment details into daily sales metrics.",
                "created_at": NOW,
            },
            {
                "upstream_table": "dws_sales_daily",
                "downstream_table": "ads_sales_report",
                "transform_desc": "Publish sales aggregates to the daily sales report.",
                "created_at": NOW,
            },
            {
                "upstream_table": "dws_sales_daily",
                "downstream_table": "ads_revenue_dashboard",
                "transform_desc": "Publish revenue metrics to dashboard.",
                "created_at": NOW,
            },
            {
                "upstream_table": "dwd_user_identity",
                "downstream_table": "ads_user_profile",
                "transform_desc": "Map stable user identity fields into user profiles.",
                "created_at": NOW,
            },
            {
                "upstream_table": "ads_user_profile",
                "downstream_table": "ads_user_profile_dashboard",
                "transform_desc": "Expose user profile coverage metrics.",
                "created_at": NOW,
            },
        ],
    )

    _insert_many(
        connection,
        "demo_scenarios",
        [
            {
                "scenario_id": "case_001_airflow_task_failed",
                "title": "Airflow task failed",
                "description": "DWD order detail task fails because a source column is missing.",
                "alert": "DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。",
                "expected_skill": "airflow_task_failed",
                "expected_root_cause": "SQL column not found: payment_status",
                "expected_tools_json": _json(["query_task_runs", "query_lineage"]),
                "created_at": NOW,
            },
            {
                "scenario_id": "case_002_partition_missing",
                "title": "Table partition missing",
                "description": "DWS sales daily partition is missing for the business date.",
                "alert": "dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。",
                "expected_skill": "partition_missing",
                "expected_root_cause": "dws_sales_daily partition dt=2026-05-14 was not produced",
                "expected_tools_json": _json(
                    ["query_table_partitions", "query_task_runs", "query_lineage"]
                ),
                "created_at": NOW,
            },
            {
                "scenario_id": "case_003_data_volume_drop",
                "title": "Data volume dropped",
                "description": "DWS sales daily row count drops by 92 percent.",
                "alert": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
                "expected_skill": "data_volume_drop",
                "expected_root_cause": "payment_orders_sync_daily failed and payment rows were missing",
                "expected_tools_json": _json(
                    [
                        "query_data_volume",
                        "query_task_runs",
                        "query_table_partitions",
                        "query_lineage",
                    ]
                ),
                "created_at": NOW,
            },
            {
                "scenario_id": "case_004_null_rate_spike",
                "title": "Null rate spiked",
                "description": "ads_user_profile.user_id null rate spikes to 35 percent.",
                "alert": "ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。",
                "expected_skill": "null_rate_spike",
                "expected_root_cause": "user identity mapping rule produced null user_id values",
                "expected_tools_json": _json(
                    ["query_null_rate", "query_task_runs", "query_lineage"]
                ),
                "created_at": NOW,
            },
        ],
    )

    _insert_many(
        connection,
        "eval_cases",
        [
            {
                "case_id": "eval_skill_airflow_task_failed_001",
                "dataset_name": "skill_match_cases",
                "input_text": "DAG dwd_order_detail_daily 今天凌晨运行失败，请帮我诊断原因。",
                "expected_skill": "airflow_task_failed",
                "expected_tools_json": _json(["query_task_runs", "query_lineage"]),
                "expected_entities_json": _json({"dag_id": "dwd_order_detail_daily"}),
                "expected_report_keywords_json": _json(["payment_status", "failed"]),
                "created_at": NOW,
            },
            {
                "case_id": "eval_skill_partition_missing_001",
                "dataset_name": "skill_match_cases",
                "input_text": "dws_sales_daily 今天没有生成 dt=2026-05-14 分区，请帮我排查。",
                "expected_skill": "partition_missing",
                "expected_tools_json": _json(
                    ["query_table_partitions", "query_task_runs", "query_lineage"]
                ),
                "expected_entities_json": _json(
                    {"table_name": "dws_sales_daily", "partition_date": BIZ_DATE}
                ),
                "expected_report_keywords_json": _json(["missing", "partition"]),
                "created_at": NOW,
            },
            {
                "case_id": "eval_skill_data_volume_drop_001",
                "dataset_name": "skill_match_cases",
                "input_text": "dws_sales_daily 今日数据量较昨日下降 92%，请判断是否存在数据事故。",
                "expected_skill": "data_volume_drop",
                "expected_tools_json": _json(
                    [
                        "query_data_volume",
                        "query_task_runs",
                        "query_table_partitions",
                        "query_lineage",
                    ]
                ),
                "expected_entities_json": _json({"table_name": "dws_sales_daily"}),
                "expected_report_keywords_json": _json(["92%", "payment_orders"]),
                "created_at": NOW,
            },
            {
                "case_id": "eval_skill_null_rate_spike_001",
                "dataset_name": "skill_match_cases",
                "input_text": "ads_user_profile 表中 user_id 字段空值率突然升高，请分析影响范围。",
                "expected_skill": "null_rate_spike",
                "expected_tools_json": _json(
                    ["query_null_rate", "query_task_runs", "query_lineage"]
                ),
                "expected_entities_json": _json(
                    {"table_name": "ads_user_profile", "field_name": "user_id"}
                ),
                "expected_report_keywords_json": _json(["null rate", "35%"]),
                "created_at": NOW,
            },
        ],
    )
