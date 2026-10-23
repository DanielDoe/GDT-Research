"""Catalog queries, scenario manifests, and compatibility checks."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from gdt_agents.contracts import DatasetContract, ScenarioCreate
from gdt_agents.db import (
    connect,
    get_dataset_row,
    init_db,
    list_datasets,
    list_observations,
)
from gdt_agents.errors import AgentError
from gdt_agents.registry import all_agents
from gdt_agents.settings import PROCESSING_VERSION
from gdt_agents.timeutil import iso_z, parse_time, utc_now

FLOOD_REQUIREMENTS = [
    {
        "role": "rainfall_forcing",
        "agent_id": "weather",
        "subagent_id": "rainfall",
        "status": "partial",
        "detail": (
            "A single-station hourly accumulation can be stored. "
            "It is not a spatial rainfall field and is not a hydrologic forcing file."
        ),
    },
    {
        "role": "coastal_water_level_boundary",
        "agent_id": "coastal",
        "subagent_id": "tidal_water_levels",
        "status": "missing",
        "detail": "NOAA CO-OPS water levels are not connected.",
    },
    {
        "role": "terrain",
        "agent_id": "geospatial_survey",
        "subagent_id": "dtm",
        "status": "missing",
        "detail": "No elevation model is registered in the catalog.",
    },
    {
        "role": "hydrodynamic_model",
        "agent_id": None,
        "subagent_id": None,
        "status": "not_configured",
        "detail": "No hydrodynamic engine is configured. A rising-water animation is not a flood model.",
    },
]


def agent_cards() -> list[dict]:
    init_db()
    cards = []
    with connect() as conn:
        for agent in all_agents():
            dataset_count = conn.execute(
                "SELECT COUNT(*) AS n FROM dataset_catalog WHERE agent_id = ?",
                (agent.id,),
            ).fetchone()["n"]
            last = conn.execute(
                """
                SELECT finished_at FROM acquisition_jobs
                WHERE agent_id = ? AND status = 'completed'
                ORDER BY finished_at DESC LIMIT 1
                """,
                (agent.id,),
            ).fetchone()
            running = conn.execute(
                """
                SELECT COUNT(*) AS n FROM acquisition_jobs
                WHERE agent_id = ? AND status IN ('queued', 'running')
                """,
                (agent.id,),
            ).fetchone()["n"]
            running += conn.execute(
                """
                SELECT COUNT(*) AS n FROM processing_jobs
                WHERE agent_id = ? AND status IN ('queued', 'running')
                """,
                (agent.id,),
            ).fetchone()["n"]
            latest = conn.execute(
                """
                SELECT status, finished_at FROM acquisition_jobs
                WHERE agent_id = ?
                ORDER BY created_at DESC LIMIT 1
                """,
                (agent.id,),
            ).fetchone()
            if agent.implementation_status == "planned":
                health = "not_implemented"
            elif latest is not None and latest["status"] == "failed":
                health = "degraded"
            elif agent.implementation_status == "limited":
                health = "limited"
            else:
                health = "ready"
            if running:
                execution = "running"
            elif latest is not None and latest["status"] == "failed":
                execution = "failed"
            else:
                execution = "idle"
            available = sum(
                1 for subagent in agent.subagents if subagent.implementation_status.value == "available"
            )
            cards.append(
                {
                    "agent_id": agent.id,
                    "name": agent.name,
                    "category": agent.category,
                    "description": agent.description,
                    "implementation_status": agent.implementation_status,
                    "subagent_count": len(agent.subagents),
                    "available_subagent_count": available,
                    "dataset_count": dataset_count,
                    "providers": agent.providers,
                    "required_credentials": agent.required_credentials,
                    "simulation_outputs": agent.simulation_outputs,
                    "last_successful_acquisition": last["finished_at"] if last else None,
                    "execution_status": execution,
                    "health_status": health,
                }
            )
    return cards


def dataset_contract(dataset_id: str) -> DatasetContract:
    init_db()
    with connect() as conn:
        row = get_dataset_row(conn, dataset_id)
    if row is None:
        raise AgentError(f"Dataset '{dataset_id}' is not in the catalog.", status_code=404)
    return DatasetContract.model_validate_json(row["contract_json"])


def dataset_observations(dataset_id: str) -> list[dict]:
    init_db()
    dataset_contract(dataset_id)
    with connect() as conn:
        return list_observations(conn, dataset_id)


def search_datasets(**filters) -> list[dict]:
    init_db()
    with connect() as conn:
        return list_datasets(conn, **filters)


def publish_layer(dataset_id: str) -> dict:
    contract = dataset_contract(dataset_id)
    if contract.spatial.representativeness != "station_point" or contract.spatial.geometry is None:
        raise AgentError("This dataset has no station point to draw.")
    coordinates = contract.spatial.geometry["coordinates"]
    descriptor = {
        "layer_id": f"layer-{dataset_id}",
        "renderer": "cesium_point",
        "dataset_id": dataset_id,
        "title": _title(contract),
        "variable": contract.variable,
        "unit": contract.measurement.unit,
        "aggregation": contract.measurement.aggregation,
        "physical_meaning": contract.measurement.physical_meaning,
        "data_kind": contract.data_kind.value,
        "source_label": _source_label(contract),
        "license": contract.provenance.license,
        "station_id": contract.source.station_id,
        "station_name": contract.source.station_name,
        "longitude": coordinates[0],
        "latitude": coordinates[1],
        "interpolation": "none",
        "representativeness": "station_point",
        "display_height_m": 40,
        "display_height_note": (
            "The marker is drawn 40 m above the ellipsoid so it remains visible. "
            "That height is not a measurement and is not an anemometer height."
        ),
        "coordinate_note": contract.spatial.coordinate_note,
        "temporal": contract.temporal.model_dump(mode="json"),
        "quality": contract.quality.model_dump(mode="json"),
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO geospatial_layers (layer_id, dataset_id, renderer, descriptor_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(layer_id) DO UPDATE SET
                descriptor_json = excluded.descriptor_json,
                created_at = excluded.created_at
            """,
            (
                descriptor["layer_id"],
                dataset_id,
                "cesium_point",
                json.dumps(descriptor),
                iso_z(utc_now()),
            ),
        )
    return descriptor


def check_compatibility(dataset_ids: list[str], purpose: str) -> dict:
    if purpose not in {"scenario", "fuse", "numerical_simulation"}:
        raise AgentError("purpose must be scenario, fuse, or numerical_simulation.")
    contracts = [dataset_contract(dataset_id) for dataset_id in dataset_ids]
    errors: list[str] = []
    warnings: list[str] = []
    if len(contracts) < 1:
        errors.append("Select at least one dataset.")
    crs = {item.spatial.crs for item in contracts}
    if len(crs) > 1:
        errors.append(f"Coordinate reference systems differ: {sorted(crs)}.")
    datums = {item.vertical.vertical_datum for item in contracts if item.vertical.vertical_datum}
    if len(datums) > 1:
        errors.append(f"Vertical datums differ: {sorted(datums)}.")
    for item in contracts:
        if item.spatial.representativeness == "station_point":
            warnings.append(
                f"{item.dataset_id} is a single station. It is not a field over the requested region "
                f"({item.spatial.requested_region_id})."
            )
        if item.quality.missing_fraction is not None and item.quality.missing_fraction > 0.5:
            warnings.append(f"{item.dataset_id} is missing more than half of its values.")
        if item.data_kind.value != "observation":
            warnings.append(f"{item.dataset_id} is {item.data_kind.value}, not an observation.")
    if purpose == "fuse":
        meanings = {item.measurement.physical_meaning for item in contracts}
        units = {item.measurement.unit for item in contracts}
        if len(meanings) > 1:
            errors.append(
                "These variables do not have the same physical meaning and were not merged: "
                + ", ".join(sorted(meanings))
            )
        if len(units) > 1:
            errors.append("Units differ. Convert them before combining values: " + ", ".join(sorted(units)))
        if any(item.spatial.representativeness == "station_point" for item in contracts):
            errors.append(
                "A station observation is not broadcast across the city. "
                "No spatial model was supplied."
            )
    intervals = [_interval(item) for item in contracts]
    if len(intervals) >= 2 and not _overlap_all(intervals):
        message = (
            "The datasets do not overlap in time. "
            "They were not interpolated, and they do not share one continuous timeline."
        )
        if purpose == "scenario":
            warnings.append(message)
        else:
            errors.append(message)
    elif len(intervals) >= 2 and not _same_bounds(intervals):
        warnings.append("Time spans only partly overlap. The timeline will not invent values outside each series.")
    if purpose == "numerical_simulation":
        errors.append(
            "No numerical simulation engine is configured. "
            "This check does not start a flood, traffic, or vehicle model."
        )
    return {
        "purpose": purpose,
        "compatible": not errors,
        "errors": errors,
        "warnings": warnings,
        "dataset_ids": dataset_ids,
        "transformations": [],
    }


def create_scenario(payload: ScenarioCreate, *, role: str) -> dict:
    init_db()
    check = check_compatibility(payload.dataset_ids, "scenario") if payload.dataset_ids else {
        "compatible": True,
        "errors": [],
        "warnings": ["No datasets are attached yet."],
        "transformations": [],
    }
    if payload.dataset_ids and not check["compatible"]:
        raise AgentError("Scenario was not saved. " + " ".join(check["errors"]), details=check)
    scenario_id = "scenario-" + uuid.uuid4().hex[:12]
    experiment_id = "experiment-" + uuid.uuid4().hex[:12]
    now = iso_z(utc_now())
    contracts = [dataset_contract(dataset_id).model_dump(mode="json") for dataset_id in payload.dataset_ids]
    manifest = {
        "experiment_id": experiment_id,
        "scenario_id": scenario_id,
        "name": payload.name,
        "objective": payload.objective,
        "category": payload.category,
        "region_id": payload.region_id,
        "mode": "visualization",
        "non_operational": True,
        "simulation_engine": None,
        "simulation_engine_version": None,
        "random_seed": None,
        "processing_version": PROCESSING_VERSION,
        "statement": (
            "This scenario displays stored datasets. "
            "It is not a numerical simulation and it is not operational decision support."
        ),
        "parameters": payload.parameters,
        "compatibility": check,
        "inputs": [
            {
                "dataset_id": item["dataset_id"],
                "variable": item["variable"],
                "data_kind": item["data_kind"],
                "processing_version": item["provenance"]["processing_version"],
                "source": item["source"],
            }
            for item in contracts
        ],
        "outputs": [],
        "evaluation_metrics": [],
        "created_at": now,
    }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO simulation_scenarios (
                scenario_id, name, category, objective, region_id, mode,
                non_operational, config_json, created_at
            ) VALUES (?, ?, ?, ?, ?, 'visualization', 1, ?, ?)
            """,
            (
                scenario_id,
                payload.name,
                payload.category,
                payload.objective,
                payload.region_id,
                json.dumps(manifest),
                now,
            ),
        )
        for dataset_id in payload.dataset_ids:
            conn.execute(
                "INSERT INTO scenario_inputs (scenario_id, dataset_id, role) VALUES (?, ?, 'primary')",
                (scenario_id, dataset_id),
            )
        conn.execute(
            """
            INSERT INTO experiment_runs (
                experiment_id, scenario_id, objective, region_id, manifest_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (experiment_id, scenario_id, payload.objective, payload.region_id, json.dumps(manifest), now),
        )
        from gdt_agents.db import audit

        audit(
            conn,
            agent_id="orchestration",
            operation="create_scenario",
            role=role,
            detail={"scenario_id": scenario_id, "dataset_ids": payload.dataset_ids},
        )
    return manifest


def list_scenarios() -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT config_json FROM simulation_scenarios ORDER BY created_at DESC"
        ).fetchall()
    return [json.loads(row["config_json"]) for row in rows]


def get_scenario(scenario_id: str) -> dict:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT config_json FROM simulation_scenarios WHERE scenario_id = ?",
            (scenario_id,),
        ).fetchone()
    if row is None:
        raise AgentError(f"Scenario '{scenario_id}' was not found.", status_code=404)
    return json.loads(row["config_json"])


def clone_scenario(scenario_id: str, *, role: str) -> dict:
    original = get_scenario(scenario_id)
    payload = ScenarioCreate(
        name=original["name"] + " (clone)",
        category=original["category"],
        objective=original["objective"],
        region_id=original["region_id"],
        dataset_ids=[item["dataset_id"] for item in original["inputs"]],
        parameters={**original.get("parameters", {}), "cloned_from": scenario_id},
    )
    return create_scenario(payload, role=role)


def compare_scenarios(left_id: str, right_id: str) -> dict:
    left = get_scenario(left_id)
    right = get_scenario(right_id)
    left_ids = {item["dataset_id"] for item in left["inputs"]}
    right_ids = {item["dataset_id"] for item in right["inputs"]}
    return {
        "left": left_id,
        "right": right_id,
        "only_left": sorted(left_ids - right_ids),
        "only_right": sorted(right_ids - left_ids),
        "shared": sorted(left_ids & right_ids),
        "note": "Comparison lists dataset identifiers. It does not score a simulation.",
    }


def validate_dataset(dataset_id: str, reference_dataset_id: str | None) -> dict:
    subject = dataset_contract(dataset_id)
    if not reference_dataset_id:
        report = {
            "dataset_id": dataset_id,
            "status": "not_validated",
            "detail": "No independent reference dataset was supplied, so no skill score was computed.",
        }
    else:
        reference = dataset_contract(reference_dataset_id)
        if subject.variable != reference.variable or subject.measurement.unit != reference.measurement.unit:
            raise AgentError(
                "The reference dataset uses a different variable or unit. Values were not compared."
            )
        subject_rows = {row["observed_at"]: row["value"] for row in dataset_observations(dataset_id)}
        reference_rows = {
            row["observed_at"]: row["value"] for row in dataset_observations(reference_dataset_id)
        }
        shared = sorted(set(subject_rows) & set(reference_rows))
        pairs = [
            (subject_rows[stamp], reference_rows[stamp])
            for stamp in shared
            if subject_rows[stamp] is not None and reference_rows[stamp] is not None
        ]
        if not pairs:
            report = {
                "dataset_id": dataset_id,
                "reference_dataset_id": reference_dataset_id,
                "status": "not_validated",
                "detail": "No overlapping numeric timestamps were found.",
                "paired_count": 0,
            }
        else:
            absolute = [abs(left - right) for left, right in pairs]
            report = {
                "dataset_id": dataset_id,
                "reference_dataset_id": reference_dataset_id,
                "status": "compared",
                "paired_count": len(pairs),
                "mean_absolute_difference": sum(absolute) / len(absolute),
                "unit": subject.measurement.unit,
                "detail": "Paired on identical timestamps only. Missing times were not interpolated.",
            }
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO quality_assessments (assessment_id, dataset_id, status, report_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "val-" + uuid.uuid4().hex[:12],
                dataset_id,
                report["status"],
                json.dumps(report),
                iso_z(utc_now()),
            ),
        )
    return report


def flood_gap_report() -> dict:
    rainfall = search_datasets(agent_id="weather", subagent_id="rainfall")
    requirements = []
    for item in FLOOD_REQUIREMENTS:
        copied = dict(item)
        if item["subagent_id"] == "rainfall" and rainfall:
            copied["status"] = "partial"
            copied["datasets"] = [entry["dataset_id"] for entry in rainfall]
        elif item["subagent_id"] == "rainfall":
            copied["status"] = "missing"
            copied["datasets"] = []
        requirements.append(copied)
    return {
        "experiment": "rainfall_and_coastal_flooding",
        "simulation_configured": False,
        "requirements": requirements,
        "statement": (
            "A flood experiment cannot be run. Station rainfall, where present, does not replace "
            "water-level boundary conditions, terrain, or a hydrodynamic model."
        ),
    }


def _interval(contract: DatasetContract) -> tuple[datetime, datetime] | None:
    if not contract.temporal.start or not contract.temporal.end:
        return None
    start = parse_time(contract.temporal.start)
    end = parse_time(contract.temporal.end)
    if end < start:
        start, end = end, start
    return start, end


def _overlap_all(intervals: list[tuple[datetime, datetime] | None]) -> bool:
    usable = [item for item in intervals if item is not None]
    if len(usable) < 2:
        return False
    start = max(item[0] for item in usable)
    end = min(item[1] for item in usable)
    return end >= start


def _same_bounds(intervals: list[tuple[datetime, datetime] | None]) -> bool:
    usable = [item for item in intervals if item is not None]
    return len({item[0] for item in usable}) == 1 and len({item[1] for item in usable}) == 1


def _title(contract: DatasetContract) -> str:
    labels = {
        "precipitation_hourly_accumulation": "Hourly precipitation accumulation",
        "wind_speed": "Wind speed",
        "wind_direction": "Wind direction",
        "wind_gust": "Wind gust",
    }
    return labels.get(contract.variable, contract.variable)


def _source_label(contract: DatasetContract) -> str:
    station = contract.source.station_id or "station"
    if contract.source.provider == "iem_asos":
        return f"NOAA ASOS via Iowa Environmental Mesonet — {station}"
    if contract.source.provider == "noaa_nws":
        return f"NOAA National Weather Service — {station}"
    return f"{contract.source.provider} — {station}"
