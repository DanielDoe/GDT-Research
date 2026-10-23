-- Galveston Digital Twin agent catalog.
-- Apply on PostgreSQL with PostGIS when that server is available:
--   psql "$DATABASE_URL" -f database/migrations/001_agent_framework.sql
-- The running API uses the SQLite catalog in data/catalog because PostGIS
-- was not available on the development workstation. Temporal indexes below
-- are btree indexes on timestamptz. No separate time-series database is required.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS agent_registry (
    agent_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    credentials_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    simulation_outputs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS subagent_registry (
    subagent_id TEXT NOT NULL,
    agent_id TEXT NOT NULL REFERENCES agent_registry (agent_id),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    definition_json JSONB NOT NULL,
    PRIMARY KEY (agent_id, subagent_id)
);

CREATE TABLE IF NOT EXISTS provider_registry (
    provider_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    documentation_url TEXT NOT NULL,
    implementation_status TEXT NOT NULL,
    auth TEXT NOT NULL,
    definition_json JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_catalog (
    dataset_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    subagent_id TEXT NOT NULL,
    variable TEXT NOT NULL,
    data_kind TEXT NOT NULL,
    processing_level TEXT NOT NULL,
    parent_dataset_id TEXT,
    contract_json JSONB NOT NULL,
    storage_uri TEXT,
    idempotency_key TEXT,
    geom geometry(Geometry, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dataset_idem
    ON dataset_catalog (idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_dataset_agent
    ON dataset_catalog (agent_id, subagent_id, variable);

CREATE INDEX IF NOT EXISTS idx_dataset_geom
    ON dataset_catalog USING GIST (geom);

CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_id TEXT PRIMARY KEY REFERENCES dataset_catalog (dataset_id),
    version_index INTEGER NOT NULL,
    parent_dataset_id TEXT,
    processing_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS dataset_provenance (
    dataset_id TEXT PRIMARY KEY REFERENCES dataset_catalog (dataset_id),
    parent_dataset_id TEXT,
    processing_version TEXT NOT NULL,
    methodology TEXT NOT NULL,
    license TEXT,
    raw_uri TEXT,
    provenance_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS acquisition_jobs (
    job_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    subagent_id TEXT,
    status TEXT NOT NULL,
    request_json JSONB NOT NULL,
    result_json JSONB,
    error TEXT,
    progress DOUBLE PRECISION NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    idempotency_key TEXT,
    depends_on_job_id TEXT,
    log TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_acq_status ON acquisition_jobs (status, created_at);

CREATE TABLE IF NOT EXISTS processing_jobs (
    LIKE acquisition_jobs INCLUDING ALL
);

CREATE INDEX IF NOT EXISTS idx_proc_status ON processing_jobs (status, created_at);

CREATE TABLE IF NOT EXISTS simulation_jobs (
    LIKE acquisition_jobs INCLUDING ALL
);

CREATE TABLE IF NOT EXISTS simulation_scenarios (
    scenario_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    objective TEXT NOT NULL,
    region_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    non_operational BOOLEAN NOT NULL DEFAULT TRUE,
    config_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scenario_inputs (
    scenario_id TEXT NOT NULL REFERENCES simulation_scenarios (scenario_id),
    dataset_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (scenario_id, dataset_id)
);

CREATE TABLE IF NOT EXISTS scenario_outputs (
    scenario_id TEXT NOT NULL REFERENCES simulation_scenarios (scenario_id),
    dataset_id TEXT NOT NULL,
    role TEXT NOT NULL,
    PRIMARY KEY (scenario_id, dataset_id, role)
);

CREATE TABLE IF NOT EXISTS geospatial_layers (
    layer_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    renderer TEXT NOT NULL,
    descriptor_json JSONB NOT NULL,
    geom geometry(Geometry, 4326),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_layers_geom ON geospatial_layers USING GIST (geom);

CREATE TABLE IF NOT EXISTS temporal_observations (
    id BIGSERIAL PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES dataset_catalog (dataset_id),
    station_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    variable TEXT NOT NULL,
    value DOUBLE PRECISION,
    unit TEXT NOT NULL,
    quality_flag TEXT,
    longitude DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    geom geometry(Point, 4326),
    row_json JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_obs_dataset_time
    ON temporal_observations (dataset_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_obs_geom ON temporal_observations USING GIST (geom);

CREATE TABLE IF NOT EXISTS agent_execution_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_id TEXT,
    operation TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    detail_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quality_assessments (
    assessment_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    status TEXT NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiment_runs (
    experiment_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL REFERENCES simulation_scenarios (scenario_id),
    objective TEXT NOT NULL,
    region_id TEXT NOT NULL,
    manifest_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
