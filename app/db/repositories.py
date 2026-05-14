from collections.abc import Sequence
import sqlite3


def rows_to_dicts(rows: Sequence[sqlite3.Row]) -> list[dict[str, object]]:
    return [dict(row) for row in rows]


class DataOpsRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def query_task_runs(
        self,
        dag_id: str | None = None,
        biz_date: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        sql = """
            SELECT
                tr.run_id,
                tr.dag_id,
                tr.task_name,
                tr.biz_date,
                tr.status,
                tr.error_type,
                tr.error_message,
                tr.log_excerpt,
                tr.retry_count,
                d.produces_table
            FROM task_runs tr
            JOIN dags d ON tr.dag_id = d.dag_id
            WHERE (? IS NULL OR tr.dag_id = ?)
              AND (? IS NULL OR tr.biz_date = ?)
              AND (? IS NULL OR tr.status = ?)
            ORDER BY tr.biz_date DESC, tr.start_time DESC
        """
        rows = self.connection.execute(
            sql, (dag_id, dag_id, biz_date, biz_date, status, status)
        ).fetchall()
        return rows_to_dicts(rows)

    def query_table_partitions(
        self,
        table_name: str,
        partition_date: str | None = None,
    ) -> list[dict[str, object]]:
        sql = """
            SELECT
                table_name,
                partition_date,
                partition_name,
                status,
                row_count,
                file_size_mb,
                error_message
            FROM table_partitions
            WHERE table_name = ?
              AND (? IS NULL OR partition_date = ?)
            ORDER BY partition_date DESC
        """
        rows = self.connection.execute(
            sql, (table_name, partition_date, partition_date)
        ).fetchall()
        return rows_to_dicts(rows)

    def query_data_volume(
        self,
        table_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, object]]:
        sql = """
            SELECT
                table_name,
                stat_date,
                row_count,
                previous_day_row_count,
                seven_day_avg_row_count,
                change_ratio,
                anomaly_flag,
                anomaly_type
            FROM data_volume_stats
            WHERE table_name = ?
              AND (? IS NULL OR stat_date >= ?)
              AND (? IS NULL OR stat_date <= ?)
            ORDER BY stat_date
        """
        rows = self.connection.execute(
            sql, (table_name, start_date, start_date, end_date, end_date)
        ).fetchall()
        return rows_to_dicts(rows)

    def query_quality_checks(
        self,
        table_name: str,
        field_name: str | None = None,
        check_type: str | None = None,
    ) -> list[dict[str, object]]:
        sql = """
            SELECT
                check_id,
                table_name,
                field_name,
                check_type,
                biz_date,
                status,
                actual_value,
                expected_value,
                threshold,
                severity,
                message
            FROM quality_checks
            WHERE table_name = ?
              AND (? IS NULL OR field_name = ?)
              AND (? IS NULL OR check_type = ?)
            ORDER BY biz_date
        """
        rows = self.connection.execute(
            sql, (table_name, field_name, field_name, check_type, check_type)
        ).fetchall()
        return rows_to_dicts(rows)

    def query_downstream_lineage(
        self,
        table_name: str,
        max_depth: int = 3,
    ) -> list[dict[str, object]]:
        sql = """
            WITH RECURSIVE downstream(table_name, depth) AS (
                SELECT downstream_table, 1
                FROM lineage_edges
                WHERE upstream_table = ?

                UNION ALL

                SELECT le.downstream_table, d.depth + 1
                FROM lineage_edges le
                JOIN downstream d ON le.upstream_table = d.table_name
                WHERE d.depth < ?
            )
            SELECT table_name, depth
            FROM downstream
            ORDER BY depth, table_name
        """
        rows = self.connection.execute(sql, (table_name, max_depth)).fetchall()
        return rows_to_dicts(rows)

