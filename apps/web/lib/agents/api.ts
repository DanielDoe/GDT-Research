export interface AgentCard {
  agent_id: string;
  name: string;
  category: string;
  description: string;
  implementation_status: string;
  subagent_count: number;
  available_subagent_count: number;
  dataset_count: number;
  providers: string[];
  last_successful_acquisition: string | null;
  execution_status: string;
  health_status: string;
}

export interface VariableSpec {
  id: string;
  name: string;
  implemented: boolean;
  note?: string | null;
  units?: string[];
  aggregation?: string | null;
}

export interface SubagentInfo {
  id: string;
  name: string;
  description: string;
  implementation_status: string;
  unavailable_reason?: string | null;
  supported_variables: VariableSpec[];
  geographic_coverage?: string;
  temporal_coverage?: string;
}

export interface DatasetContract {
  dataset_id: string;
  agent_id: string;
  subagent_id: string;
  variable: string;
  data_kind: string;
  source: {
    provider: string;
    dataset: string;
    source_url?: string | null;
    station_id?: string | null;
    station_name?: string | null;
  };
  spatial: {
    crs: string;
    geometry: { type: string; coordinates: number[] } | null;
    representativeness: string;
    coordinate_note?: string | null;
  };
  temporal: {
    start: string | null;
    end: string | null;
    resolution: string | null;
  };
  measurement: {
    unit: string;
    aggregation: string;
    physical_meaning: string;
  };
  quality: {
    status: string;
    missing_fraction: number | null;
    trace_count?: number | null;
    observation_count?: number | null;
    notes?: string[];
    uncertainty?: string | null;
  };
  provenance: {
    license?: string | null;
    methodology?: string;
    processing_version?: string;
  };
}

export interface ObservationRow {
  observed_at: string;
  value: number | null;
  quality_flag: string | null;
  unit: string;
  variable: string;
  longitude: number;
  latitude: number;
  station_id: string;
  station_name?: string | null;
}

export interface JobRecord {
  job_id: string;
  kind: string;
  status: string;
  error: string | null;
  progress: number;
  result: {
    datasets?: Array<{ dataset_id: string; contract: DatasetContract }>;
    provider?: string;
    failover_from?: string;
  } | null;
}

function apiBase(): string {
  const configured = (process.env.NEXT_PUBLIC_GDT_API_BASE ?? "").trim().replace(/\/$/, "");
  if (configured) return configured;
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host === "localhost" || host === "127.0.0.1") return "http://127.0.0.1:8000";
  }
  return "";
}

export function datasetDownloadUrl(datasetId: string): string {
  return `${apiBase()}/api/v1/datasets/${datasetId}/download`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-GDT-Role": "researcher",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    const base = apiBase();
    throw new Error(
      base
        ? `The research API is not reachable at ${base}. Start it with: .\\.venv\\Scripts\\python.exe -m uvicorn services.api.main:app --host 127.0.0.1 --port 8000`
        : "The research catalog on this site did not respond. Reload the page.",
    );
  }
  const text = await response.text();
  const body = text ? (JSON.parse(text) as { detail?: string }) : {};
  if (!response.ok) {
    throw new Error(body.detail || response.statusText);
  }
  return body as T;
}

export function listAgents() {
  return request<{ agents: AgentCard[] }>("/api/v1/agents");
}

export function getAgent(agentId: string) {
  return request<{ card: AgentCard; subagents: SubagentInfo[] }>(`/api/v1/agents/${agentId}`);
}

export function runOperation(payload: {
  agent_id: string;
  subagent_id: string;
  operation: string;
  region_id?: string;
  time_range?: { start: string; end: string };
  parameters?: Record<string, unknown>;
}) {
  return request<{ jobs?: JobRecord[]; result?: unknown }>("/api/v1/agents/operations", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getJob(jobId: string) {
  return request<JobRecord>(`/api/v1/jobs/${jobId}`);
}

export function getObservations(datasetId: string) {
  return request<{ observations: ObservationRow[] }>(`/api/v1/datasets/${datasetId}/observations`);
}

export function publishDataset(datasetId: string) {
  return request<{
    title: string;
    variable: string;
    unit: string;
    aggregation: string;
    data_kind: string;
    source_label: string;
    license: string | null;
    station_id: string;
    station_name: string;
    longitude: number;
    latitude: number;
    display_height_note: string;
    representativeness: string;
  }>(`/api/v1/datasets/${datasetId}/publish`, { method: "POST" });
}

export function createScenario(payload: {
  name: string;
  objective: string;
  category?: string;
  region_id?: string;
  dataset_ids: string[];
  parameters?: Record<string, unknown>;
}) {
  return request<{
    scenario_id: string;
    name: string;
    mode: string;
    statement: string;
    inputs: Array<{ dataset_id: string }>;
    compatibility: { warnings: string[]; errors: string[] };
  }>("/api/v1/scenarios", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function waitForJob(jobId: string): Promise<JobRecord> {
  for (let attempt = 0; attempt < 90; attempt += 1) {
    const job = await getJob(jobId);
    if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error("The job is still running. Leave this page open or check job status in the API.");
}
