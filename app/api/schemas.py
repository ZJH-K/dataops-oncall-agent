from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiOptions(BaseModel):
    stream: bool = False
    save_incident: bool = True
    debug: bool = False


class DiagnoseRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    alert: str = Field(..., min_length=1)
    options: ApiOptions = Field(default_factory=ApiOptions)


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)


class SkillMatchRequest(BaseModel):
    alert: str = Field(..., min_length=1)
    debug: bool = False


class ToolInvokeRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
