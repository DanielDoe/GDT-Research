"""Agent registry, weather parsing, jobs, and scenario checks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from gdt_agents.contracts import AgentOperation, AgentOperationRequest, TimeRange
from gdt_agents.errors import AgentError
from gdt_agents.jobs import cancel_job, enqueue, get_job, run_once, set_executor
from gdt_agents.processing.crs import transform_point
from gdt_agents.processing.units import inches_to_mm, knots_to_ms
from gdt_agents.providers.iem_asos import apply_calm_direction, parse_asos_csv
from gdt_agents.providers.noaa_nws import parse_observations
from gdt_agents.registry import get_agent, get_subagent
from gdt_agents.weather_pipeline import acquire_weather, process_weather

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MIGRATION = ROOT / "database" / "migrations" / "001_agent_framework.sql"

REQUIRED_TABLES = [
    "agent_registry",
    "subagent_registry",
    "provider_registry",
    "dataset_catalog",
    "dataset_versions",
    "dataset_provenance",
    "acquisition_jobs",
    "processing_jobs",
    "simulation_jobs",
    "simulation_scenarios",
    "scenario_inputs",
    "scenario_outputs",
    "geospatial_layers",
    "temporal_observations",
    "agent_execution_logs",
    "quality_assessments",
    "experiment_runs",
]


@pytest.fixture(autouse=True)
def isolated_catalog(tmp_path, monkeypatch):
    monkeypatch.setenv("GDT_DATA_ROOT", str(tmp_path))
    yield
    set_executor(None)


def test_registry_marks_only_rainfall_and_wind_available() -> None:
    weather = get_agent("weather")
    assert weather is not None
    available = {item.id for item in weather.subagents if item.implementation_status.value == "available"}
    assert available == {"rainfall", "wind"}
    temperature = get_subagent("weather", "temperature")
    assert temperature is not None
    assert temperature.implementation_status.value == "unavailable"
    satellite = get_agent("satellite")
    assert satellite is not None
    assert satellite.implementation_status == "planned"
    assert all(item.implementation_status.value == "unavailable" for item in satellite.subagents)


def test_migration_declares_catalog_tables() -> None:
    sql = MIGRATION.read_text(encoding="utf-8").lower()
    for name in REQUIRED_TABLES:
        assert name in sql
    assert "postgis" in sql
    assert "timescaledb" not in sql


def test_iem_fixture_preserves_trace_and_converts_accumulation() -> None:
    body = (FIXTURES / "iem_asos_gls_hourly_sample.csv").read_bytes()
    start = datetime(2024, 7, 7, tzinfo=timezone.utc)
    end = datetime(2024, 7, 8, tzinfo=timezone.utc)
    rows = parse_asos_csv(
        body,
        variables={"precipitation_hourly_accumulation"},
        start=start,
        end=end,
    )
    flags = {row.observed_at: row for row in rows}
    trace = flags["2024-07-07T05:52:00Z"]
    assert trace.value is None
    assert trace.quality_flag == "trace"
    assert trace.aggregation == "hourly_accumulation"
    measured = flags["2024-07-07T06:52:00Z"]
    assert measured.value == pytest.approx(0.03)
    assert measured.unit == "in"
    assert inches_to_mm(0.03) == pytest.approx(0.762)


def test_nws_fixture_uses_station_coordinates_not_rounded_point() -> None:
    document = json.loads((FIXTURES / "nws_kgls_observations_sample.json").read_text(encoding="utf-8"))
    station = {
        "geometry": {"type": "Point", "coordinates": [-94.86417, 29.27028]},
        "properties": {
            "stationIdentifier": "KGLS",
            "name": "Galveston, Scholes Field",
            "elevation": {"unitCode": "wmoUnit:m", "value": 2.1336},
        },
    }
    start = datetime(2026, 10, 23, 14, tzinfo=timezone.utc)
    end = datetime(2026, 10, 23, 16, tzinfo=timezone.utc)
    rows = parse_observations(document["features"], station, start=start, end=end)
    speeds = [row for row in rows if row.variable == "wind_speed"]
    assert speeds
    assert speeds[0].longitude == pytest.approx(-94.86417)
    assert speeds[0].latitude == pytest.approx(29.27028)
    assert speeds[0].unit == "km/h"
    precip = [row for row in rows if row.variable == "precipitation_hourly_accumulation"]
    assert precip
    assert all(row.value is None for row in precip)


def test_calm_wind_direction_is_not_stored_as_north() -> None:
    from gdt_agents.contracts import ObservationRow

    rows = [
        ObservationRow(
            station_id="GLS",
            longitude=-94.86,
            latitude=29.26,
            observed_at="2024-07-07T00:52:00Z",
            variable="wind_speed",
            physical_meaning="wind_speed",
            value=0.0,
            unit="kt",
            aggregation="instantaneous_report",
        ),
        ObservationRow(
            station_id="GLS",
            longitude=-94.86,
            latitude=29.26,
            observed_at="2024-07-07T00:52:00Z",
            variable="wind_direction",
            physical_meaning="wind_direction",
            value=0.0,
            unit="degree",
            aggregation="instantaneous_report",
        ),
    ]
    apply_calm_direction(rows)
    assert rows[1].value is None
    assert rows[1].quality_flag == "calm"
    assert knots_to_ms(10) == pytest.approx(1852 / 360)


def test_recorded_asos_acquire_and_process_keeps_provenance(isolated_catalog) -> None:
    body = (FIXTURES / "iem_asos_gls_hourly_sample.csv").read_bytes()

    def fetcher(_url: str) -> bytes:
        return body

    acquired = acquire_weather(
        subagent_id="rainfall",
        region_id="galveston-downtown",
        parameters={"provider": "iem_asos", "station_id": "KGLS", "_fetcher": fetcher},
        time_range={"start": "2024-07-07T00:00:00Z", "end": "2024-07-08T00:00:00Z"},
        job_key="test-rainfall",
        progress=lambda *_args: None,
        cancelled=lambda: None,
    )
    raw = acquired["datasets"][0]["contract"]
    assert raw["data_kind"] == "observation"
    assert raw["measurement"]["aggregation"] == "hourly_accumulation"
    assert raw["measurement"]["unit"] == "in"
    assert raw["spatial"]["representativeness"] == "station_point"
    assert raw["quality"]["trace_count"] == 1
    assert "downtown" in (raw["spatial"]["coordinate_note"] or "").lower() or raw["spatial"]["geometry"]["coordinates"][0] < -94.8
    processed = process_weather(
        subagent_id="rainfall",
        parameters={"source_dataset_id": raw["dataset_id"], "preferred_unit": "mm"},
        job={"depends_on_job_id": None},
        progress=lambda *_args: None,
        cancelled=lambda: None,
    )
    contract = processed["datasets"][0]["contract"]
    assert contract["measurement"]["unit"] == "mm"
    assert contract["provenance"]["parent_dataset_id"] == raw["dataset_id"]
    assert contract["data_kind"] == "observation"
    from gdt_agents.catalog_ops import dataset_observations

    rows = dataset_observations(contract["dataset_id"])
    by_time = {row["observed_at"]: row for row in rows}
    assert by_time["2024-07-07T06:52:00Z"]["value"] == pytest.approx(0.762)
    assert by_time["2024-07-07T05:52:00Z"]["value"] is None
    assert by_time["2024-07-07T05:52:00Z"]["quality_flag"] == "trace"
    assert by_time["2024-07-07T05:52:00Z"]["unit"] == "mm"


def test_intensity_request_is_rejected() -> None:
    with pytest.raises(AgentError, match="intensity"):
        acquire_weather(
            subagent_id="rainfall",
            region_id="galveston-downtown",
            parameters={"provider": "iem_asos", "preferred_unit": "mm/h"},
            time_range={"start": "2024-07-07T00:00:00Z", "end": "2024-07-08T00:00:00Z"},
            job_key="nope",
            progress=lambda *_args: None,
            cancelled=lambda: None,
        )


def test_unavailable_subagent_is_not_queued() -> None:
    from gdt_agents.runner import submit_operation

    result_error = None
    try:
        submit_operation(
            AgentOperationRequest(
                agent_id="weather",
                subagent_id="temperature",
                operation=AgentOperation.acquire,
                time_range=TimeRange(start="2024-07-07T00:00:00Z", end="2024-07-08T00:00:00Z"),
            )
        )
    except AgentError as exc:
        result_error = str(exc)
    assert result_error is not None
    assert "not implemented" in result_error.lower()


def test_job_retries_then_succeeds() -> None:
    calls = {"n": 0}

    def executor(job, progress, _cancelled):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient provider failure")
        progress(1, "done")
        return {"ok": True}

    set_executor(executor)
    request = AgentOperationRequest(
        agent_id="weather",
        subagent_id="wind",
        operation=AgentOperation.acquire,
        parameters={"token": "retry-case"},
    )
    job = enqueue(request, kind="acquire", max_attempts=2)
    assert run_once() is True
    assert get_job(job["job_id"])["status"] == "queued"
    assert run_once() is True
    finished = get_job(job["job_id"])
    assert finished["status"] == "completed"
    assert finished["result"]["ok"] is True


def test_queued_job_can_be_cancelled_before_it_runs() -> None:
    called = {"n": 0}

    def executor(_job, _progress, _cancelled):
        called["n"] += 1
        return {"ok": True}

    set_executor(executor)
    request = AgentOperationRequest(
        agent_id="weather",
        subagent_id="wind",
        operation=AgentOperation.acquire,
        parameters={"token": "cancel-case"},
    )
    job = enqueue(request, kind="acquire")
    cancel_job(job["job_id"])
    assert run_once() is False
    assert get_job(job["job_id"])["status"] == "cancelled"
    assert called["n"] == 0


def test_scenario_accepts_station_series_and_refuses_fake_fusion() -> None:
    from gdt_agents.catalog_ops import check_compatibility, create_scenario
    from gdt_agents.contracts import ScenarioCreate

    body = (FIXTURES / "iem_asos_gls_hourly_sample.csv").read_bytes()
    acquired = acquire_weather(
        subagent_id="rainfall",
        region_id="galveston-downtown",
        parameters={"provider": "iem_asos", "station_id": "GLS", "_fetcher": lambda _url: body},
        time_range={"start": "2024-07-07T00:00:00Z", "end": "2024-07-08T00:00:00Z"},
        job_key="scenario-rainfall",
        progress=lambda *_args: None,
        cancelled=lambda: None,
    )
    dataset_id = acquired["datasets"][0]["dataset_id"]
    check = check_compatibility([dataset_id], "scenario")
    assert check["compatible"] is True
    assert any("single station" in warning.lower() for warning in check["warnings"])
    fuse = check_compatibility([dataset_id], "fuse")
    assert fuse["compatible"] is False
    simulation = check_compatibility([dataset_id], "numerical_simulation")
    assert simulation["compatible"] is False
    manifest = create_scenario(
        ScenarioCreate(
            name="Scholes Field hourly rainfall",
            objective="Inspect observed hourly accumulation. This is not a flood model.",
            dataset_ids=[dataset_id],
            parameters={"requested_selections": [{"agent_id": "coastal", "status": "unavailable"}]},
        ),
        role="researcher",
    )
    assert manifest["mode"] == "visualization"
    assert manifest["simulation_engine"] is None
    assert manifest["non_operational"] is True
    assert manifest["inputs"][0]["dataset_id"] == dataset_id


def test_assistant_does_not_invent_elevation_or_rainfall() -> None:
    from gdt_agents.assistant import ask

    elevation = ask("Which elevation dataset has the best coverage?")
    assert elevation["model"] is None
    assert elevation["jobs_started"] is False
    assert "no elevation" in elevation["answer"].lower()
    rainfall = ask("What rainfall datasets are available for Galveston?")
    assert "no rainfall dataset" in rainfall["answer"].lower()
    flood = ask("Which datasets are missing for a flood experiment?")
    assert flood["jobs_started"] is False
    assert "cannot be run" in flood["answer"].lower() or "not configured" in flood["answer"].lower()


def test_crs_round_trip_for_scholes_field() -> None:
    longitude, latitude = -94.8604, 29.2653
    easting, northing = transform_point(longitude, latitude, "EPSG:4326", "EPSG:32615")
    back_lon, back_lat = transform_point(easting, northing, "EPSG:32615", "EPSG:4326")
    assert abs(back_lon - longitude) < 1e-6
    assert abs(back_lat - latitude) < 1e-6


def test_api_lists_agents_and_keeps_health() -> None:
    from fastapi.testclient import TestClient
    from services.api.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        listed = client.get("/api/v1/agents")
        assert listed.status_code == 200
        ids = {item["agent_id"] for item in listed.json()["agents"]}
        assert "weather" in ids
        assert "satellite" in ids
        weather = client.get("/api/v1/agents/weather")
        assert weather.status_code == 200
        statuses = {item["id"]: item["implementation_status"] for item in weather.json()["subagents"]}
        assert statuses["rainfall"] == "available"
        assert statuses["temperature"] == "unavailable"
        refused = client.post(
            "/api/v1/agents/operations",
            json={
                "agent_id": "satellite",
                "subagent_id": "optical",
                "operation": "acquire",
            },
        )
        assert refused.status_code == 409


@pytest.mark.integration
def test_live_iem_and_nws_galveston_observations() -> None:
    rainfall = acquire_weather(
        subagent_id="rainfall",
        region_id="galveston-downtown",
        parameters={"provider": "iem_asos", "station_id": "KGLS"},
        time_range={"start": "2024-07-07T00:00:00Z", "end": "2024-07-07T08:00:00Z"},
        job_key="live-iem-rainfall",
        progress=lambda *_args: None,
        cancelled=lambda: None,
    )
    rain = rainfall["datasets"][0]["contract"]
    assert rain["data_kind"] == "observation"
    assert rain["source"]["provider"] == "iem_asos"
    assert (rain["quality"]["observation_count"] or 0) >= 1
    assert rain["spatial"]["geometry"]["coordinates"][0] < -94.8

    wind = acquire_weather(
        subagent_id="wind",
        region_id="galveston-downtown",
        parameters={"provider": "noaa_nws", "station_id": "KGLS", "lookback_hours": 6},
        time_range=None,
        job_key="live-nws-wind",
        progress=lambda *_args: None,
        cancelled=lambda: None,
    )
    speed = next(item["contract"] for item in wind["datasets"] if item["contract"]["variable"] == "wind_speed")
    assert speed["data_kind"] == "observation"
    assert speed["source"]["provider"] == "noaa_nws"
    assert speed["spatial"]["geometry"]["coordinates"][0] == pytest.approx(-94.86417, abs=0.01)
