"""Dispatch agent operations.

Acquisition and processing enter the job queue. Describe, discover, and status
stay synchronous. Numerical simulation is refused.
"""

from __future__ import annotations

from gdt_agents.catalog_ops import publish_layer, validate_dataset
from gdt_agents.contracts import AgentOperation, AgentOperationRequest
from gdt_agents.db import connect, init_db
from gdt_agents.errors import AgentError
from gdt_agents.jobs import enqueue
from gdt_agents.registry import get_agent, get_subagent
from gdt_agents.timeutil import iso_z, utc_now
from gdt_agents.weather_pipeline import acquire_weather, discover_weather, process_weather


def submit_operation(request: AgentOperationRequest) -> dict:
    if request.operation == AgentOperation.cancel:
        raise AgentError("Cancel a job with POST /api/v1/jobs/{job_id}/cancel.")
    agent = get_agent(request.agent_id)
    if agent is None:
        raise AgentError(f"Unknown agent '{request.agent_id}'.", status_code=404)
    if request.subagent_id:
        subagent = get_subagent(request.agent_id, request.subagent_id)
        if subagent is None:
            raise AgentError(
                f"Unknown subagent '{request.subagent_id}' on '{request.agent_id}'.",
                status_code=404,
            )
    if request.operation in {AgentOperation.acquire, AgentOperation.process}:
        return _enqueue_work(request)
    return {"result": run_sync(request)}


def execute_job(job: dict, progress, cancelled) -> dict:
    request = AgentOperationRequest.model_validate(job["request"])
    if job["kind"] == "acquire":
        if request.agent_id != "weather" or not request.subagent_id:
            raise AgentError(
                "Only Weather rainfall and wind can be acquired. Other agents are registered and have no connector."
            )
        return acquire_weather(
            subagent_id=request.subagent_id,
            region_id=request.region_id,
            parameters=request.parameters,
            time_range=request.time_range.model_dump() if request.time_range else None,
            job_key=job.get("idempotency_key") or job["job_id"],
            progress=progress,
            cancelled=cancelled,
        )
    if job["kind"] == "process":
        return process_weather(
            subagent_id=request.subagent_id or "weather",
            parameters=request.parameters,
            job=job,
            progress=progress,
            cancelled=cancelled,
        )
    raise AgentError("No numerical simulation engine is configured, so this job was not run.")


def run_sync(request: AgentOperationRequest) -> dict:
    operation = request.operation
    if operation == AgentOperation.describe:
        return _describe(request.agent_id, request.subagent_id)
    if operation == AgentOperation.get_status:
        from gdt_agents.catalog_ops import agent_cards

        cards = [card for card in agent_cards() if card["agent_id"] == request.agent_id]
        return {"agent": cards[0] if cards else None}
    if operation == AgentOperation.discover:
        return _discover(request)
    if operation == AgentOperation.configure:
        return _configure(request)
    if operation == AgentOperation.validate:
        dataset_id = request.parameters.get("dataset_id")
        if not dataset_id:
            raise AgentError("validate requires parameters.dataset_id.")
        return validate_dataset(str(dataset_id), request.parameters.get("reference_dataset_id"))
    if operation == AgentOperation.publish:
        dataset_id = request.parameters.get("dataset_id")
        if not dataset_id:
            raise AgentError("publish requires parameters.dataset_id.")
        return publish_layer(str(dataset_id))
    raise AgentError(f"Operation '{operation.value}' is not available.")


def _enqueue_work(request: AgentOperationRequest) -> dict:
    if request.agent_id != "weather":
        raise AgentError(
            f"Agent '{request.agent_id}' has no acquisition connector. Nothing was queued.",
            status_code=409,
        )
    subagent = get_subagent("weather", request.subagent_id or "")
    if subagent is None or subagent.implementation_status.value != "available":
        raise AgentError(
            "That subagent is not implemented. No job was queued and no values were estimated.",
            status_code=409,
        )
    if request.operation == AgentOperation.acquire and request.parameters.get("workflow") == "acquire_and_process":
        params = {key: value for key, value in request.parameters.items() if key != "workflow"}
        acquire_request = request.model_copy(
            update={"operation": AgentOperation.acquire, "parameters": params}
        )
        acquire_job = enqueue(acquire_request, kind="acquire")
        if acquire_job["status"] == "failed":
            return {"jobs": [acquire_job]}
        process_request = request.model_copy(
            update={
                "operation": AgentOperation.process,
                "parameters": {
                    "from_dependency": True,
                    "preferred_unit": params.get("preferred_unit"),
                },
            }
        )
        process_job = enqueue(process_request, kind="process", depends_on=acquire_job["job_id"])
        return {"jobs": [acquire_job, process_job]}
    kind = "acquire" if request.operation == AgentOperation.acquire else "process"
    return {"jobs": [enqueue(request, kind=kind)]}


def _describe(agent_id: str, subagent_id: str | None) -> dict:
    agent = get_agent(agent_id)
    if agent is None:
        raise AgentError(f"Unknown agent '{agent_id}'.", status_code=404)
    if subagent_id:
        subagent = get_subagent(agent_id, subagent_id)
        if subagent is None:
            raise AgentError(f"Unknown subagent '{subagent_id}'.", status_code=404)
        return {"subagent": subagent.model_dump(mode="json")}
    return {"agent": agent.model_dump(mode="json")}


def _discover(request: AgentOperationRequest) -> dict:
    if request.agent_id == "weather" and request.subagent_id:
        return discover_weather(request.subagent_id, live=bool(request.parameters.get("live")))
    agent = get_agent(request.agent_id)
    if agent is None:
        raise AgentError(f"Unknown agent '{request.agent_id}'.", status_code=404)
    return {
        "agent_id": agent.id,
        "implementation_status": agent.implementation_status,
        "subagents": [item.model_dump(mode="json") for item in agent.subagents],
        "live": None,
        "note": "No provider connector is implemented for this agent, so discovery did not invent datasets.",
    }


def _configure(request: AgentOperationRequest) -> dict:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT agent_id FROM agent_registry WHERE agent_id = ?",
            (request.agent_id,),
        ).fetchone()
        if row is None:
            raise AgentError(f"Unknown agent '{request.agent_id}'.", status_code=404)
        conn.execute(
            "UPDATE agent_registry SET config_json = ?, updated_at = ? WHERE agent_id = ?",
            (request.model_dump_json(), iso_z(utc_now()), request.agent_id),
        )
    return {"agent_id": request.agent_id, "stored": True, "note": "Configuration was stored. It does not fetch data."}
