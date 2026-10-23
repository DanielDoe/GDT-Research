"""Typed contracts for agents, datasets, jobs, and scenarios."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ImplementationStatus(str, Enum):
    available = "available"
    unavailable = "unavailable"
    limited = "limited"


class DataKind(str, Enum):
    observation = "observation"
    forecast = "forecast"
    reanalysis = "reanalysis"
    satellite_estimate = "satellite_estimate"
    interpolated = "interpolated"
    model_generated = "model_generated"
    synthetic_demonstration = "synthetic_demonstration"


class AgentOperation(str, Enum):
    discover = "discover"
    describe = "describe"
    configure = "configure"
    acquire = "acquire"
    validate = "validate"
    process = "process"
    publish = "publish"
    get_status = "get_status"
    cancel = "cancel"


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class PhysicalMeaning(str, Enum):
    precipitation_hourly_accumulation = "precipitation_hourly_accumulation"
    wind_speed = "wind_speed"
    wind_direction = "wind_direction"
    wind_gust = "wind_gust"


class SourceRef(BaseModel):
    provider: str
    dataset: str
    source_url: str | None = None
    station_id: str | None = None
    station_name: str | None = None


class SpatialRef(BaseModel):
    crs: str = "EPSG:4326"
    geometry: dict[str, Any] | None = None
    resolution: str | None = None
    representativeness: str = "station_point"
    requested_region_id: str | None = None
    coordinate_note: str | None = None
    reported_observation_geometry: dict[str, Any] | None = None


class VerticalRef(BaseModel):
    station_elevation_m: float | None = None
    vertical_datum: str | None = None
    note: str | None = None


class TemporalRef(BaseModel):
    start: str | None = None
    end: str | None = None
    resolution: str | None = None
    requested_start: str | None = None
    requested_end: str | None = None
    alignment: str = "provider_timestamp_not_resampled"


class MeasurementRef(BaseModel):
    unit: str
    aggregation: str
    physical_meaning: str
    preferred_unit: str | None = None
    source_unit: str | None = None


class QualityRef(BaseModel):
    status: str
    missing_fraction: float | None = None
    uncertainty: str | None = None
    trace_count: int | None = None
    suspect_count: int | None = None
    observation_count: int | None = None
    notes: list[str] = Field(default_factory=list)


class StorageRef(BaseModel):
    format: str
    uri: str | None = None


class ProvenanceRef(BaseModel):
    processing_version: str
    license: str | None = None
    methodology: str
    parent_dataset_id: str | None = None
    acquired_at: str | None = None
    model_version: str | None = None
    raw_uri: str | None = None
    failover_from: str | None = None
    failover_reason: str | None = None


class DatasetContract(BaseModel):
    dataset_id: str
    agent_id: str
    subagent_id: str
    variable: str
    data_kind: DataKind
    source: SourceRef
    spatial: SpatialRef
    vertical: VerticalRef = Field(default_factory=VerticalRef)
    temporal: TemporalRef
    measurement: MeasurementRef
    quality: QualityRef
    storage: StorageRef
    provenance: ProvenanceRef
    processing_level: str


class ObservationRow(BaseModel):
    station_id: str
    station_name: str | None = None
    longitude: float
    latitude: float
    observed_at: str
    variable: str
    physical_meaning: str
    value: float | None
    unit: str
    aggregation: str
    provider_qc: str | None = None
    quality_flag: str | None = None


class TimeRange(BaseModel):
    start: str
    end: str


class AgentOperationRequest(BaseModel):
    agent_id: str
    subagent_id: str | None = None
    operation: AgentOperation
    region_id: str = "galveston-downtown"
    time_range: TimeRange | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class VariableSpec(BaseModel):
    id: str
    name: str
    physical_meaning: str
    implemented: bool
    units: list[str]
    aggregation: str | None = None
    note: str | None = None


class SubagentDefinition(BaseModel):
    id: str
    name: str
    parent_agent_id: str
    description: str
    implementation_status: ImplementationStatus
    unavailable_reason: str | None = None
    supported_variables: list[VariableSpec] = Field(default_factory=list)
    data_providers: list[str] = Field(default_factory=list)
    required_parameters: list[str] = Field(default_factory=list)
    output_schemas: list[str] = Field(default_factory=list)
    geographic_coverage: str
    temporal_coverage: str
    units: list[str] = Field(default_factory=list)
    processing_requirements: list[str] = Field(default_factory=list)
    simulation_compatibility: list[str] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    id: str
    name: str
    category: str
    description: str
    implementation_status: str
    subagents: list[SubagentDefinition]
    providers: list[str] = Field(default_factory=list)
    simulation_outputs: list[str] = Field(default_factory=list)
    required_credentials: list[str] = Field(default_factory=list)


class ProviderDefinition(BaseModel):
    id: str
    name: str
    documentation_url: str
    implementation_status: ImplementationStatus
    auth: str
    credentials_env: list[str] = Field(default_factory=list)
    data_kinds: list[str] = Field(default_factory=list)
    notes: str
    license: str | None = None


class ScenarioInput(BaseModel):
    dataset_id: str
    role: str = "primary"


class ScenarioCreate(BaseModel):
    name: str
    category: str = "data_inspection"
    objective: str
    region_id: str = "galveston-downtown"
    dataset_ids: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AssistantQuestion(BaseModel):
    question: str
