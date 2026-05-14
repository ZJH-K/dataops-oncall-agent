from dataclasses import asdict, dataclass
from typing import Any, Literal


ToolStatus = Literal["success", "failed"]


@dataclass(frozen=True)
class ToolResponse:
    tool_call_id: str
    tool_name: str
    status: ToolStatus
    latency_ms: int
    result_summary: str
    result: dict[str, Any] | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

