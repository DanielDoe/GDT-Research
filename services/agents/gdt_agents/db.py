"""SQLite catalog.

The PostGIS migration in database/migrations is the production schema. This
workstation path is used because a PostGIS server was not available. Table
names match the migration. Geometry is stored as GeoJSON text.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from gdt_agents.contracts import AgentDefinition, DatasetContract, ProviderDefinition
from gdt_agents.registry import PROVIDERS, all_agents
from gdt_agents.settings import catalog_db_path
from gdt_agents.timeutil import iso_z, utc_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_registry (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    credentials_json TEXT NOT NULL DEFAULT '[]',
    simulation_outputs_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subagent_registry (
    subagent_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    PRIMARY KEY (agent_id, subagent_id)
);

CREATE TABLE IF NOT EXISTS provider_registry (
    provider_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    documentation_url TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    auth TEXT NOT NULL,
    definition_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_catalog (
    dataset_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    subagent_id TEXT NOT NULL,
    variable TEXT NOT NULL,
    data_kind TEXT NOT NULL,
    processing_level TEXT NOT NULL,
    parent_dataset_id TEXT,
    contract_json TEXT NOT NULL,
    storage_uri TEXT,
    idempotency_key TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_id TEXT PRIMARY KEY,
    version_index INTEGER NOT NULL,
    parent_dataset_id TEXT,
    processing_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_provenance (
    dataset_id TEXT PRIMARY KEY,
    parent_dataset_id TEXT,
    processing_version TEXT NOT NULL,
    methodology TEXT NOT NULL,
    license TEXT,
    raw_uri TEXT,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS acquisition_jobs (
    job_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    subagent_id TEXT,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    progress REAL NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    idempotency_key TEXT,
    depends_on_job_id TEXT,
    log TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    job_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    subagent_id TEXT,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    progress REAL NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    idempotency_key TEXT,
    depends_on_job_id TEXT,
    log TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS simulation_jobs (
    job_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    subagent_id TEXT,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    progress REAL NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    idempotency_key TEXT,
    depends_on_job_id TEXT,
    log TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS simulation_scenarios (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    objective TEXT NOT NULL,
    region_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    non_operational INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_inputs (
    scenario_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (scenario_id, dataset_id)
);

CREATE TABLE IF NOT EXISTS scenario_outputs (
    scenario_id TEXT NOT NULL,
    dataset_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (scenario_id, dataset_id, role)
);

CREATE TABLE IF NOT EXISTS geospatial_layers (
    layer_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    renderer TEXT NOT NULL,
    descriptor_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS temporal_observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id TEXT NOT NULL,
    station_id TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    variable TEXT NOT NULL,
    value REAL,
    unit TEXT NOT NULL,
    quality_flag TEXT,
    longitude REAL NOT NULL,
    latitude REAL NOT NULL,
    row_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_dataset_time
    ON temporal_observations (dataset_id, observed_at);

CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT,
    operation TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quality_assessments (
    assessment_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    status TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    experiment_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    objective TEXT NOT NULL,
    region_id TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dataset_idem
    ON dataset_catalog (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_dataset_agent
    ON dataset_catalog (agent_id, subagent_id, variable);
CREATE INDEX IF NOT EXISTS idx_acq_status ON acquisition_jobs (status, created_at);
CREATE INDEX IF NOT EXISTS idx_proc_status ON processing_jobs (status, created_at);
"""

JOB_TABLES = {
    "acquire": "acquisition_jobs",
    "process": "processing_jobs",
    "simulate": "simulation_jobs",
}


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), default=str)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(catalog_db_path(), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def init_db() -> None:
    conn = sqlite3.connect(catalog_db_path(), timeout=30)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    with connect() as conn:
        _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    now = iso_z(utc_now())
    for agent in all_agents():
        _upsert_agent(conn, agent, now)
    for provider in PROVIDERS:
        conn.execute(
            """
            INSERT INTO provider_registry (
                provider_id, name, documentation_url, implementation_status, auth, definition_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(provider_id) DO UPDATE SET
                name = excluded.name,
                documentation_url = excluded.documentation_url,
                implementation_status = excluded.implementation_status,
                auth = excluded.auth,
                definition_json = excluded.definition_json
            """,
            (
                provider.id,
                provider.name,
                provider.documentation_url,
                provider.implementation_status.value,
                provider.auth,
                provider.model_dump_json(),
            ),
        )


def _upsert_agent(conn: sqlite3.Connection, agent: AgentDefinition, now: str) -> None:
    conn.execute(
        """
        INSERT INTO agent_registry (
            agent_id, name, category, description, implementation_status,
            credentials_json, simulation_outputs_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id) DO UPDATE SET
            name = excluded.name,
            category = excluded.category,
            description = excluded.description,
            implementation_status = excluded.implementation_status,
            credentials_json = excluded.credentials_json,
            simulation_outputs_json = excluded.simulation_outputs_json,
            updated_at = excluded.updated_at
        """,
        (
            agent.id,
            agent.name,
            agent.category,
            agent.description,
            agent.implementation_status,
            _json(agent.required_credentials),
            _json(agent.simulation_outputs),
            now,
        ),
    )
    for subagent in agent.subagents:
        conn.execute(
            """
            INSERT INTO subagent_registry (
                subagent_id, agent_id, name, description, implementation_status, definition_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(agent_id, subagent_id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                implementation_status = excluded.implementation_status,
                definition_json = excluded.definition_json
            """,
            (
                subagent.id,
                agent.id,
                subagent.name,
                subagent.description,
                subagent.implementation_status.value,
                subagent.model_dump_json(),
            ),
        )


def audit(conn: sqlite3.Connection, *, agent_id: str | None, operation: str, role: str, detail: dict) -> None:
    conn.execute(
        """
        INSERT INTO agent_execution_logs (agent_id, operation, actor_role, detail_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (agent_id, operation, role, _json(detail), iso_z(utc_now())),
    )


def insert_dataset(
    conn: sqlite3.Connection,
    contract: DatasetContract,
    rows: list[dict],
    *,
    idempotency_key: str | None,
) -> None:
    now = iso_z(utc_now())
    conn.execute(
        """
        INSERT INTO dataset_catalog (
            dataset_id, agent_id, subagent_id, variable, data_kind, processing_level,
            parent_dataset_id, contract_json, storage_uri, idempotency_key, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            contract.dataset_id,
            contract.agent_id,
            contract.subagent_id,
            contract.variable,
            contract.data_kind.value,
            contract.processing_level,
            contract.provenance.parent_dataset_id,
            contract.model_dump_json(),
            contract.storage.uri,
            idempotency_key,
            now,
        ),
    )
    version_index = 1 if contract.processing_level == "raw" else 2
    conn.execute(
        """
        INSERT INTO dataset_versions (
            dataset_id, version_index, parent_dataset_id, processing_version, created_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            contract.dataset_id,
            version_index,
            contract.provenance.parent_dataset_id,
            contract.provenance.processing_version,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO dataset_provenance (
            dataset_id, parent_dataset_id, processing_version, methodology, license,
            raw_uri, provenance_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            contract.dataset_id,
            contract.provenance.parent_dataset_id,
            contract.provenance.processing_version,
            contract.provenance.methodology,
            contract.provenance.license,
            contract.provenance.raw_uri,
            contract.provenance.model_dump_json(),
            now,
        ),
    )
    conn.executemany(
        """
        INSERT INTO temporal_observations (
            dataset_id, station_id, observed_at, variable, value, unit, quality_flag,
            longitude, latitude, row_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                contract.dataset_id,
                row["station_id"],
                row["observed_at"],
                row["variable"],
                row["value"],
                row["unit"],
                row.get("quality_flag"),
                row["longitude"],
                row["latitude"],
                _json(row),
            )
            for row in rows
        ],
    )


def dataset_by_idempotency(conn: sqlite3.Connection, key: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM dataset_catalog WHERE idempotency_key = ?",
        (key,),
    ).fetchone()


def get_dataset_row(conn: sqlite3.Connection, dataset_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM dataset_catalog WHERE dataset_id = ?",
        (dataset_id,),
    ).fetchone()


def list_observations(conn: sqlite3.Connection, dataset_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT row_json FROM temporal_observations
        WHERE dataset_id = ?
        ORDER BY observed_at
        """,
        (dataset_id,),
    ).fetchall()
    return [json.loads(row["row_json"]) for row in rows]


def list_datasets(
    conn: sqlite3.Connection,
    *,
    agent_id: str | None = None,
    subagent_id: str | None = None,
    variable: str | None = None,
) -> list[dict]:
    clauses = []
    params: list[str] = []
    if agent_id:
        clauses.append("agent_id = ?")
        params.append(agent_id)
    if subagent_id:
        clauses.append("subagent_id = ?")
        params.append(subagent_id)
    if variable:
        clauses.append("variable = ?")
        params.append(variable)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT contract_json FROM dataset_catalog {where} ORDER BY created_at DESC",
        params,
    ).fetchall()
    return [json.loads(row["contract_json"]) for row in rows]


def job_table(kind: str) -> str:
    try:
        return JOB_TABLES[kind]
    except KeyError as exc:
        raise KeyError(kind) from exc


def row_to_job(row: sqlite3.Row, kind: str) -> dict:
    return {
        "job_id": row["job_id"],
        "kind": kind,
        "agent_id": row["agent_id"],
        "subagent_id": row["subagent_id"],
        "status": row["status"],
        "request": json.loads(row["request_json"]),
        "result": json.loads(row["result_json"]) if row["result_json"] else None,
        "error": row["error"],
        "progress": row["progress"],
        "attempts": row["attempts"],
        "max_attempts": row["max_attempts"],
        "idempotency_key": row["idempotency_key"],
        "depends_on_job_id": row["depends_on_job_id"],
        "log": row["log"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


def find_job(conn: sqlite3.Connection, job_id: str) -> dict | None:
    for kind, table in JOB_TABLES.items():
        row = conn.execute(f"SELECT * FROM {table} WHERE job_id = ?", (job_id,)).fetchone()
        if row is not None:
            return row_to_job(row, kind)
    return None


def find_job_by_idempotency(conn: sqlite3.Connection, kind: str, key: str) -> dict | None:
    table = job_table(kind)
    row = conn.execute(
        f"""
        SELECT * FROM {table}
        WHERE idempotency_key = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (key,),
    ).fetchone()
    return row_to_job(row, kind) if row else None
