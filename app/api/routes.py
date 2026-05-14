from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.schemas import ChatRequest, DiagnoseRequest, SkillMatchRequest
from app.api.services import (
    answer_chat,
    api_error,
    api_success,
    check_health,
    diagnose_alert,
    format_diagnosis_response,
    get_incident,
    get_incident_tool_calls,
    get_skill_detail,
    list_incidents,
    list_skills,
    match_skill,
)
from app.rag.indexer import DEFAULT_INDEX_PATH


router = APIRouter(prefix="/api")


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    return api_success(
        check_health(
            database_url=_database_url(request),
            index_path=_rag_index_path(request),
        )
    )


@router.post("/diagnose")
def diagnose(request: Request, payload: DiagnoseRequest) -> JSONResponse:
    try:
        state = diagnose_alert(
            session_id=payload.session_id,
            alert=payload.alert,
            database_url=_database_url(request),
            index_path=_rag_index_path(request),
            debug=payload.options.debug,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=api_error(
                code=500,
                message="diagnosis failed",
                error_type="internal_error",
                detail=str(exc),
            ),
        )

    data = format_diagnosis_response(state)
    if state.get("needs_clarification"):
        return JSONResponse(
            status_code=422,
            content={
                "code": 422,
                "message": "clarification required",
                "data": data,
            },
        )
    return JSONResponse(status_code=200, content=api_success(data))


@router.post("/diagnose/stream")
def diagnose_stream(request: Request, payload: DiagnoseRequest) -> StreamingResponse:
    def event_generator():
        yield _sse("status", {"stage": "started", "session_id": payload.session_id})
        try:
            state = diagnose_alert(
                session_id=payload.session_id,
                alert=payload.alert,
                database_url=_database_url(request),
                index_path=_rag_index_path(request),
                debug=True,
            )
            yield _sse("alert_context", state.get("alert_context", {}))
            if state.get("needs_clarification"):
                yield _sse(
                    "clarification_required",
                    {
                        "question": state.get("clarification_question"),
                        "candidates": state.get("candidate_diagnosis_skills", []),
                    },
                )
                yield _sse(
                    "completed",
                    {
                        "incident_id": state.get("incident_id"),
                        "status": "needs_clarification",
                    },
                )
                return

            yield _sse("skill_matched", state.get("selected_diagnosis_skill", {}))
            yield _sse("docs_retrieved", state.get("retrieved_docs", []))
            yield _sse("plan_created", state.get("plan", []))
            for call in state.get("tool_calls", []):
                event_type = (
                    "tool_call_failed"
                    if call.get("status") == "failed"
                    else "tool_call_completed"
                )
                yield _sse(event_type, call)
            yield _sse("coverage_checked", state.get("coverage_result", {}))
            yield _sse("report_delta", {"content": state.get("final_report", "")})
            yield _sse(
                "completed",
                {"incident_id": state.get("incident_id"), "status": "completed"},
            )
        except Exception as exc:
            yield _sse(
                "error",
                {"type": "internal_error", "detail": str(exc)},
            )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/chat")
def chat(request: Request, payload: ChatRequest) -> JSONResponse:
    data = answer_chat(
        database_url=_database_url(request),
        session_id=payload.session_id,
        message=payload.message,
    )
    if data is None:
        return JSONResponse(
            status_code=404,
            content=api_error(
                code=404,
                message="session not found",
                error_type="not_found",
                detail=f"session not found: {payload.session_id}",
            ),
        )
    return JSONResponse(status_code=200, content=api_success(data))


@router.get("/skills")
def skills() -> dict[str, Any]:
    return api_success({"skills": list_skills()})


@router.get("/skills/{skill_name}")
def skill_detail(skill_name: str) -> JSONResponse:
    data = get_skill_detail(skill_name)
    if data is None:
        return JSONResponse(
            status_code=404,
            content=api_error(
                code=404,
                message="skill not found",
                error_type="not_found",
                detail=f"Diagnosis Skill not found: {skill_name}",
            ),
        )
    return JSONResponse(status_code=200, content=api_success(data))


@router.post("/skills/match")
def skills_match(payload: SkillMatchRequest) -> dict[str, Any]:
    return api_success(match_skill(payload.alert))


@router.get("/incidents")
def incidents(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    skill_name: str | None = None,
) -> dict[str, Any]:
    return api_success(
        list_incidents(
            database_url=_database_url(request),
            page=page,
            page_size=page_size,
            skill_name=skill_name,
        )
    )


@router.get("/incidents/{incident_id}")
def incident_detail(request: Request, incident_id: str) -> JSONResponse:
    data = get_incident(_database_url(request), incident_id)
    if data is None:
        return JSONResponse(
            status_code=404,
            content=api_error(
                code=404,
                message="incident not found",
                error_type="not_found",
                detail=f"incident not found: {incident_id}",
            ),
        )
    return JSONResponse(status_code=200, content=api_success(data))


@router.get("/incidents/{incident_id}/tool-calls")
def incident_tool_calls(request: Request, incident_id: str) -> JSONResponse:
    tool_calls = get_incident_tool_calls(_database_url(request), incident_id)
    if tool_calls is None:
        return JSONResponse(
            status_code=404,
            content=api_error(
                code=404,
                message="incident not found",
                error_type="not_found",
                detail=f"incident not found: {incident_id}",
            ),
        )
    return JSONResponse(
        status_code=200,
        content=api_success({"incident_id": incident_id, "tool_calls": tool_calls}),
    )


def _database_url(request: Request) -> str | None:
    return getattr(request.app.state, "database_url", None)


def _rag_index_path(request: Request) -> Path:
    return Path(getattr(request.app.state, "rag_index_path", DEFAULT_INDEX_PATH))


def _sse(event: str, data: Any) -> str:
    return (
        f"event: {event}\n"
        f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"
    )
