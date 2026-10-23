"""HTTP routes for the agent catalog, jobs, and scenarios."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse

from gdt_agents.catalog_ops import (
    agent_cards,
    check_compatibility,
    clone_scenario,
    compare_scenarios,
    create_scenario,
    dataset_contract,
    dataset_observations,
    flood_gap_report,
    get_scenario,
    list_scenarios,
    publish_layer,
    search_datasets,
)
from gdt_agents.contracts import AgentOperationRequest, AssistantQuestion, ScenarioCreate
from gdt_agents.db import audit, connect, init_db
from gdt_agents.errors import AgentError
from gdt_agents.jobs import cancel_job, get_job, list_jobs, retry_job
from gdt_agents.registry import PROVIDERS, get_agent
from gdt_agents.runner import submit_operation
from gdt_agents.settings import data_root

router = APIRouter(prefix="/api/v1")


def _role(request: Request) -> str:
    role = request.headers.get("x-gdt-role", "researcher")
    if role not in {"researcher", "admin"}:
        raise HTTPException(status_code=403, detail="Unknown role.")
    return role


def agent_error_response(exc: AgentError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc), "details": exc.details},
    )


@router.get("/agents")
def list_agent_cards() -> dict:
    cards = agent_cards()
    return {"agents": cards}


@router.get("/agents/{agent_id}")
def agent_detail(agent_id: str) -> dict:
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'.")
    card = next((item for item in agent_cards() if item["agent_id"] == agent_id), None)
    return {
        "card": card,
        "subagents": [item.model_dump(mode="json") for item in agent.subagents],
    }


@router.get("/providers")
def list_providers() -> dict:
    return {"providers": [item.model_dump(mode="json") for item in PROVIDERS]}


@router.post("/agents/operations")
def operations(payload: AgentOperationRequest, request: Request) -> dict:
    role = _role(request)
    try:
        result = submit_operation(payload)
    except AgentError as exc:
        return agent_error_response(exc)
    init_db()
    with connect() as conn:
        audit(
            conn,
            agent_id=payload.agent_id,
            operation=payload.operation.value,
            role=role,
            detail={"subagent_id": payload.subagent_id, "region_id": payload.region_id},
        )
    return result


@router.get("/jobs")
def jobs(limit: int = Query(default=40, ge=1, le=200)) -> dict:
    return {"jobs": list_jobs(limit)}


@router.get("/jobs/{job_id}")
def job_detail(job_id: str) -> dict:
    try:
        return get_job(job_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str, request: Request) -> dict:
    role = _role(request)
    try:
        job = cancel_job(job_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    with connect() as conn:
        audit(conn, agent_id=job["agent_id"], operation="cancel", role=role, detail={"job_id": job_id})
    return job


@router.post("/jobs/{job_id}/retry")
def job_retry(job_id: str, request: Request) -> dict:
    role = _role(request)
    try:
        job = retry_job(job_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    with connect() as conn:
        audit(conn, agent_id=job["agent_id"], operation="retry", role=role, detail={"job_id": job_id})
    return job


@router.get("/datasets")
def datasets(
    agent_id: str | None = None,
    subagent_id: str | None = None,
    variable: str | None = None,
) -> dict:
    return {"datasets": search_datasets(agent_id=agent_id, subagent_id=subagent_id, variable=variable)}


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: str) -> dict:
    try:
        contract = dataset_contract(dataset_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return contract.model_dump(mode="json")


@router.get("/datasets/{dataset_id}/observations")
def observations(dataset_id: str) -> dict:
    try:
        rows = dataset_observations(dataset_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return {"dataset_id": dataset_id, "observations": rows}


@router.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: str):
    try:
        contract = dataset_contract(dataset_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    if not contract.storage.uri:
        raise HTTPException(status_code=404, detail="This dataset has no file.")
    path = _safe_data_file(contract.storage.uri)
    return FileResponse(path, media_type="text/csv", filename=f"{dataset_id}.csv")


@router.post("/datasets/{dataset_id}/publish")
def publish(dataset_id: str, request: Request) -> dict:
    role = _role(request)
    try:
        layer = publish_layer(dataset_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    with connect() as conn:
        audit(conn, agent_id="visualization", operation="publish", role=role, detail={"dataset_id": dataset_id})
    return layer


@router.post("/datasets/{dataset_id}/validate")
def validate(dataset_id: str, reference_dataset_id: str | None = None) -> dict:
    try:
        return validate_dataset(dataset_id, reference_dataset_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/compatibility/check")
def compatibility(payload: dict) -> dict:
    dataset_ids = payload.get("dataset_ids") or []
    purpose = payload.get("purpose") or "scenario"
    if not isinstance(dataset_ids, list):
        raise HTTPException(status_code=400, detail="dataset_ids must be a list.")
    try:
        return check_compatibility([str(item) for item in dataset_ids], str(purpose))
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/scenarios")
def scenario_create(payload: ScenarioCreate, request: Request) -> dict:
    role = _role(request)
    try:
        manifest = create_scenario(payload, role=role)
    except AgentError as exc:
        return agent_error_response(exc)
    return manifest


@router.get("/scenarios")
def scenario_list() -> dict:
    return {"scenarios": list_scenarios()}


@router.get("/scenarios/compare")
def scenario_compare(left: str = Query(), right: str = Query()) -> dict:
    try:
        return compare_scenarios(left, right)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/scenarios/{scenario_id}")
def scenario_detail(scenario_id: str) -> dict:
    try:
        return get_scenario(scenario_id)
    except AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/scenarios/{scenario_id}/clone")
def scenario_clone(scenario_id: str, request: Request) -> dict:
    role = _role(request)
    try:
        return clone_scenario(scenario_id, role=role)
    except AgentError as exc:
        return agent_error_response(exc)


@router.get("/orchestration/flood-gaps")
def flood_gaps() -> dict:
    return flood_gap_report()


@router.post("/assistant/ask")
def assistant_ask(payload: AssistantQuestion) -> dict:
    from gdt_agents.assistant import ask
    from gdt_agents.errors import AgentError as _AgentError

    try:
        return ask(payload.question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except _AgentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _safe_data_file(uri: str) -> Path:
    path = Path(uri).resolve()
    root = data_root().resolve()
    if path != root and root not in path.parents:
        raise HTTPException(status_code=400, detail="Dataset path is outside the data directory.")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dataset file is missing.")
    return path
