from typing import Any, Protocol


class DataOpsToolProvider(Protocol):
    def query_task_runs(
        self,
        task_name: str | None = None,
        table_name: str | None = None,
        date: str | None = None,
        status: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

    def query_table_partitions(
        self,
        table_name: str,
        date: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

    def query_data_volume(
        self,
        table_name: str,
        start_date: str | None = None,
        end_date: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

    def query_null_rate(
        self,
        table_name: str,
        field_name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

    def query_lineage(
        self,
        table_name: str,
        direction: str = "downstream",
        depth: int = 3,
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

    def create_incident_report(
        self,
        report_payload: dict[str, Any],
        session_id: str = "demo_session",
        incident_id: str | None = None,
        run_id: str | None = None,
    ) -> dict[str, Any]: ...

