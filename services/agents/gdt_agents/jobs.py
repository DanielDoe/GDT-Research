"""Durable job queue.

Redis and Celery are not required. SQLite is the queue because it is present
on this workstation and survives a process restart. A single worker thread
drains acquisition and processing jobs. Simulation jobs are rejected.
"""

from __future__ import annotations

import hashlib
import json
import threading
import traceback
import uuid
from typing import Callable

from gdt_agents.contracts import AgentOperationRequest, JobState
from gdt_agents.db import JOB_TABLES, connect, find_job, find_job_by_idempotency, init_db, job_table
from gdt_agents.errors import AgentError, JobCancelled, ProviderError
from gdt_agents.settings import PROCESSING_VERSION
from gdt_agents.timeutil import iso_z, utc_now

Executor = Callable[[dict, Callable[[float, str], None], Callable[[], None]], dict]

_executor_box: dict[str, Executor] = {}
_worker_lock = threading.Lock()
_stop = threading.Event()
_thread: threading.Thread | None = None


def set_executor(function: Executor | None) -> None:
    if function is None:
        _executor_box.pop("fn", None)
    else:
        _executor_box["fn"] = function


def _default_executor(job: dict, progress: Callable[[float, str], None], cancelled: Callable[[], None]) -> dict:
    from gdt_agents.runner import execute_job

    return execute_job(job, progress, cancelled)


def enqueue(request: AgentOperationRequest, *, kind: str, depends_on: str | None = None, max_attempts: int = 3) -> dict:
    init_db()
    key = None if request.parameters.get("force") else idempotency_key(kind, request, depends_on)
    with connect() as conn:
        if key:
            existing = find_job_by_idempotency(conn, kind, key)
            if existing and existing["status"] != JobState.cancelled.value:
                return existing
        job_id = "job-" + uuid.uuid4().hex[:16]
        now = iso_z(utc_now())
        table = job_table(kind)
        conn.execute(
            f"""
            INSERT INTO {table} (
                job_id, agent_id, subagent_id, status, request_json, progress,
                attempts, max_attempts, idempotency_key, depends_on_job_id,
                log, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, ?, '', ?, ?)
            """,
            (
                job_id,
                request.agent_id,
                request.subagent_id,
                JobState.queued.value,
                request.model_dump_json(),
                max_attempts,
                key,
                depends_on,
                now,
                now,
            ),
        )
        stored = find_job(conn, job_id)
    if stored is None:
        raise AgentError("Job was inserted but could not be read back.")
    return stored


def idempotency_key(kind: str, request: AgentOperationRequest, depends_on: str | None) -> str:
    parameters = {
        name: value
        for name, value in sorted(request.parameters.items())
        if name not in {"force", "_fetcher"} and not name.startswith("_")
    }
    payload = {
        "kind": kind,
        "agent_id": request.agent_id,
        "subagent_id": request.subagent_id,
        "region_id": request.region_id,
        "time_range": request.time_range.model_dump(mode="json") if request.time_range else None,
        "parameters": parameters,
        "depends_on": depends_on,
        "processing_version": PROCESSING_VERSION,
    }
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def run_once() -> bool:
    init_db()
    claimed = _claim()
    if claimed is None:
        return False
    job, kind = claimed
    progress, cancelled = _callbacks(job["job_id"], kind)

    def wrapped_progress(fraction: float, message: str) -> None:
        progress(fraction, message)
        cancelled()

    try:
        executor = _executor_box.get("fn", _default_executor)
        result = executor(job, wrapped_progress, cancelled)
        _finish(kind, job["job_id"], JobState.completed.value, result=result, error=None)
    except JobCancelled:
        _finish(kind, job["job_id"], JobState.cancelled.value, result=None, error="Cancelled.")
    except ProviderError as exc:
        _fail_or_retry(kind, job, str(exc), retryable=exc.retryable)
    except AgentError as exc:
        _fail_or_retry(kind, job, str(exc), retryable=False)
    except Exception as exc:  # noqa: BLE001 — job log must keep the traceback
        _append_log(kind, job["job_id"], traceback.format_exc())
        _fail_or_retry(kind, job, str(exc), retryable=True)
    return True


def cancel_job(job_id: str) -> dict:
    init_db()
    with connect() as conn:
        job = find_job(conn, job_id)
        if job is None:
            raise AgentError(f"Job '{job_id}' was not found.", status_code=404)
        if job["status"] in {JobState.completed.value, JobState.failed.value, JobState.cancelled.value}:
            return job
        table = job_table(job["kind"])
        now = iso_z(utc_now())
        conn.execute(
            f"""
            UPDATE {table}
            SET status = ?, error = ?, updated_at = ?, finished_at = ?
            WHERE job_id = ? AND status IN ('queued', 'running')
            """,
            (JobState.cancelled.value, "Cancelled.", now, now, job_id),
        )
        updated = find_job(conn, job_id)
    if updated is None:
        raise AgentError(f"Job '{job_id}' was not found.", status_code=404)
    return updated


def retry_job(job_id: str) -> dict:
    init_db()
    with connect() as conn:
        job = find_job(conn, job_id)
        if job is None:
            raise AgentError(f"Job '{job_id}' was not found.", status_code=404)
        if job["status"] not in {JobState.failed.value, JobState.cancelled.value}:
            raise AgentError("Only a failed or cancelled job can be retried.")
        table = job_table(job["kind"])
        now = iso_z(utc_now())
        conn.execute(
            f"""
            UPDATE {table}
            SET status = ?, error = NULL, finished_at = NULL, progress = 0, attempts = 0, updated_at = ?
            WHERE job_id = ?
            """,
            (JobState.queued.value, now, job_id),
        )
        updated = find_job(conn, job_id)
    if updated is None:
        raise AgentError(f"Job '{job_id}' was not found.", status_code=404)
    return updated


def get_job(job_id: str) -> dict:
    init_db()
    with connect() as conn:
        job = find_job(conn, job_id)
    if job is None:
        raise AgentError(f"Job '{job_id}' was not found.", status_code=404)
    return job


def list_jobs(limit: int = 50) -> list[dict]:
    init_db()
    jobs: list[dict] = []
    with connect() as conn:
        for kind, table in JOB_TABLES.items():
            rows = conn.execute(
                f"SELECT * FROM {table} ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            from gdt_agents.db import row_to_job

            jobs.extend(row_to_job(row, kind) for row in rows)
    jobs.sort(key=lambda item: item["created_at"], reverse=True)
    return jobs[:limit]


def start_worker() -> None:
    global _thread
    with _worker_lock:
        if _thread and _thread.is_alive():
            return
        _stop.clear()
        _thread = threading.Thread(target=_loop, name="gdt-job-worker", daemon=True)
        _thread.start()


def shutdown_worker() -> None:
    _stop.set()
    thread = _thread
    if thread and thread.is_alive():
        thread.join(timeout=2)


def _loop() -> None:
    while not _stop.is_set():
        try:
            worked = run_once()
        except Exception:
            traceback.print_exc()
            worked = False
        if not worked:
            _stop.wait(0.4)


def _claim() -> tuple[dict, str] | None:
    from gdt_agents.db import row_to_job

    with connect() as conn:
        for kind, table in JOB_TABLES.items():
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE status = 'queued' ORDER BY created_at"
            ).fetchall()
            for row in rows:
                job = row_to_job(row, kind)
                if not _dependency_ready(conn, job):
                    continue
                now = iso_z(utc_now())
                cursor = conn.execute(
                    f"""
                    UPDATE {table}
                    SET status = 'running', attempts = attempts + 1, started_at = ?, updated_at = ?, progress = 0.05
                    WHERE job_id = ? AND status = 'queued'
                    """,
                    (now, now, job["job_id"]),
                )
                if cursor.rowcount != 1:
                    continue
                job["status"] = "running"
                job["attempts"] = job["attempts"] + 1
                return job, kind
    return None


def _dependency_ready(conn, job: dict) -> bool:
    depends = job.get("depends_on_job_id")
    if not depends:
        return True
    parent = find_job(conn, depends)
    if parent is None or parent["status"] in {JobState.queued.value, JobState.running.value}:
        return False
    if parent["status"] != JobState.completed.value:
        table = job_table(job["kind"])
        now = iso_z(utc_now())
        conn.execute(
            f"""
            UPDATE {table}
            SET status = 'failed', error = ?, updated_at = ?, finished_at = ?
            WHERE job_id = ? AND status = 'queued'
            """,
            (f"Dependency {depends} ended with status {parent['status']}.", now, now, job["job_id"]),
        )
        return False
    return True


def _callbacks(job_id: str, kind: str):
    def progress(fraction: float, message: str) -> None:
        table = job_table(kind)
        now = iso_z(utc_now())
        with connect() as conn:
            row = conn.execute(f"SELECT status, log FROM {table} WHERE job_id = ?", (job_id,)).fetchone()
            if row is None or row["status"] == JobState.cancelled.value:
                raise JobCancelled()
            log = (row["log"] or "") + f"{now} {message}\n"
            conn.execute(
                f"UPDATE {table} SET progress = ?, log = ?, updated_at = ? WHERE job_id = ? AND status = 'running'",
                (max(0.0, min(1.0, fraction)), log, now, job_id),
            )

    def cancelled() -> None:
        table = job_table(kind)
        with connect() as conn:
            row = conn.execute(f"SELECT status FROM {table} WHERE job_id = ?", (job_id,)).fetchone()
            if row is None or row["status"] == JobState.cancelled.value:
                raise JobCancelled()

    return progress, cancelled


def _finish(kind: str, job_id: str, status: str, *, result: dict | None, error: str | None) -> None:
    table = job_table(kind)
    now = iso_z(utc_now())
    with connect() as conn:
        conn.execute(
            f"""
            UPDATE {table}
            SET status = ?, result_json = ?, error = ?, progress = ?, updated_at = ?, finished_at = ?
            WHERE job_id = ? AND status = 'running'
            """,
            (
                status,
                json.dumps(result, default=str) if result is not None else None,
                error,
                1 if status == JobState.completed.value else 0,
                now,
                now,
                job_id,
            ),
        )


def _fail_or_retry(kind: str, job: dict, message: str, *, retryable: bool) -> None:
    if retryable and job["attempts"] < job["max_attempts"]:
        table = job_table(kind)
        now = iso_z(utc_now())
        with connect() as conn:
            conn.execute(
                f"""
                UPDATE {table}
                SET status = 'queued', error = ?, updated_at = ?, finished_at = NULL
                WHERE job_id = ? AND status = 'running'
                """,
                (message, now, job["job_id"]),
            )
        return
    _finish(kind, job["job_id"], JobState.failed.value, result=None, error=message)


def _append_log(kind: str, job_id: str, text: str) -> None:
    table = job_table(kind)
    with connect() as conn:
        row = conn.execute(f"SELECT log FROM {table} WHERE job_id = ?", (job_id,)).fetchone()
        if row is None:
            return
        conn.execute(
            f"UPDATE {table} SET log = ? WHERE job_id = ?",
            ((row["log"] or "") + text + "\n", job_id),
        )
