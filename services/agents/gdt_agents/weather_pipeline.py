"""Acquire and standardize Galveston station weather observations."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gdt_agents.contracts import (
    DatasetContract,
    DataKind,
    MeasurementRef,
    ObservationRow,
    ProvenanceRef,
    QualityRef,
    SourceRef,
    SpatialRef,
    StorageRef,
    TemporalRef,
    VerticalRef,
)
from gdt_agents.db import connect, dataset_by_idempotency, get_dataset_row, insert_dataset, list_observations
from gdt_agents.errors import AgentError, ProviderError
from gdt_agents.processing.qc import assess_rows
from gdt_agents.processing.units import convert_length, convert_speed, round_scientific
from gdt_agents.providers.iem_asos import apply_calm_direction, fetch_reports
from gdt_agents.providers.noaa_nws import fetch_observations, station_location_note
from gdt_agents.registry import get_provider, get_subagent
from gdt_agents.settings import MAX_ACQUISITION_DAYS, PROCESSING_VERSION, data_root, study_area_path
from gdt_agents.timeutil import ensure_range, iso_z, parse_time, utc_now

STATION_PATTERN = re.compile(r"^[A-Za-z0-9]{3,10}$")
RAINFALL_METHODOLOGY = (
    "Routine hourly ASOS reports are read from the selected provider. "
    "For IEM, report_type=3 avoids mixing special reports that repeat the same hourly accumulation. "
    "The ASOS field p01i is precipitation over the hour ending at the report time, in inches. "
    "It is stored as hourly accumulation and is not converted to intensity. "
    "Trace (T) stays a null value with quality_flag=trace. "
    "Missing (M) stays null and is not replaced with zero. "
    "Report timestamps are kept as sent; they are not moved onto clock hours and gaps are not interpolated. "
    "Millimetres are inches multiplied by 25.4. "
    "The geometry is the station point reported by the provider, not the downtown study polygon."
)
WIND_METHODOLOGY = (
    "Station wind reports are read from the selected provider. "
    "Speed is converted to metres per second: 1 knot = 1852/3600 m/s, and 1 km/h = 1/3.6 m/s. "
    "Direction is the direction the wind is coming from, in degrees. "
    "A calm report (speed 0 and direction 0) stores a null direction with quality_flag=calm. "
    "A direction of 0 with nonzero speed remains north. "
    "Missing gusts stay missing. "
    "Timestamps are not interpolated. "
    "The NWS observation GeoJSON point is often rounded to 0.1 degree and is not used when the station document has coordinates. "
    "No anemometer height is assigned unless the provider file contains one."
)


def variables_for(subagent_id: str) -> list[str]:
    if subagent_id == "rainfall":
        return ["precipitation_hourly_accumulation"]
    if subagent_id == "wind":
        return ["wind_speed", "wind_direction", "wind_gust"]
    raise AgentError(f"Weather subagent '{subagent_id}' cannot acquire data.")


def resolve_window(parameters: dict, time_range: dict | None) -> tuple[datetime, datetime]:
    if time_range is not None:
        start = parse_time(time_range["start"])
        end = parse_time(time_range["end"])
        ensure_range(start, end, max_days=MAX_ACQUISITION_DAYS)
        return start, end
    lookback = parameters.get("lookback_hours")
    if lookback is None:
        raise AgentError(
            "Provide time_range in UTC or parameters.lookback_hours. "
            "A historical storm interval is not assumed."
        )
    try:
        hours = int(lookback)
    except (TypeError, ValueError) as exc:
        raise AgentError("lookback_hours must be an integer.") from exc
    if hours < 1 or hours > 24 * MAX_ACQUISITION_DAYS:
        raise AgentError(f"lookback_hours must be between 1 and {24 * MAX_ACQUISITION_DAYS}.")
    end = utc_now()
    return end - timedelta(hours=hours), end


def acquire_weather(
    *,
    subagent_id: str,
    region_id: str,
    parameters: dict,
    time_range: dict | None,
    job_key: str,
    progress,
    cancelled,
) -> dict:
    subagent = get_subagent("weather", subagent_id)
    if subagent is None or subagent.implementation_status.value != "available":
        raise AgentError(
            f"Subagent '{subagent_id}' is not available. No data was generated for it.",
            status_code=409,
        )
    provider_id = str(parameters.get("provider") or _default_provider(subagent_id))
    provider = get_provider(provider_id)
    if provider is None or provider.implementation_status.value != "available":
        raise AgentError(f"Provider '{provider_id}' is not an implemented weather connector.", status_code=400)
    station_id = str(parameters.get("station_id") or "KGLS")
    if not STATION_PATTERN.fullmatch(station_id):
        raise AgentError("station_id must be 3 to 10 letters or digits.")
    start, end = resolve_window(parameters, time_range)
    variables = variables_for(subagent_id)
    preferred_unit = parameters.get("preferred_unit")
    _reject_intensity_request(parameters, preferred_unit)
    cancelled()
    progress(0.15, f"Requesting {provider_id} for station {station_id}.")
    bundle = _download(
        provider_id,
        station_id,
        start,
        end,
        variables,
        fetcher=parameters.get("_fetcher"),
        cancelled=cancelled,
    )
    progress(0.55, "Parsing provider records.")
    stored = _persist_bundle(
        bundle,
        variables=variables,
        region_id=region_id,
        job_key=job_key,
        level="raw",
        preferred_unit=None,
    )
    result = {
        "provider": provider_id,
        "station_id": station_id,
        "requested_start": iso_z(start),
        "requested_end": iso_z(end),
        "datasets": stored,
        "data_kind": DataKind.observation.value,
    }
    failover = parameters.get("failover_provider")
    if (
        subagent_id == "rainfall"
        and provider_id == "noaa_nws"
        and failover == "iem_asos"
        and _no_numeric_values(stored)
    ):
        progress(0.7, "NOAA NWS precipitation values are missing. Requesting IEM ASOS observations.")
        fallback = _download(
            "iem_asos",
            station_id,
            start,
            end,
            variables,
            fetcher=parameters.get("_fetcher"),
            cancelled=cancelled,
        )
        fallback["failover_from"] = "noaa_nws"
        fallback["failover_reason"] = (
            "The NOAA NWS observation documents did not contain precipitation values for this request. "
            "IEM ASOS hourly accumulation was requested because failover_provider was set."
        )
        fallback_stored = _persist_bundle(
            fallback,
            variables=variables,
            region_id=region_id,
            job_key=job_key + ":failover",
            level="raw",
            preferred_unit=None,
        )
        result["datasets"] = fallback_stored
        result["unused_datasets"] = stored
        result["failover_from"] = "noaa_nws"
        result["provider"] = "iem_asos"
    progress(1.0, "Acquisition stored.")
    return result


def process_weather(
    *,
    subagent_id: str,
    parameters: dict,
    job: dict,
    progress,
    cancelled,
) -> dict:
    source_ids = list(parameters.get("source_dataset_ids") or [])
    if parameters.get("from_dependency"):
        parent = _dependency_result(job)
        source_ids = [item["dataset_id"] for item in parent.get("datasets") or []]
    if not source_ids and parameters.get("source_dataset_id"):
        source_ids = [parameters["source_dataset_id"]]
    if not source_ids:
        raise AgentError("Process requires source_dataset_id or a completed acquisition dependency.")
    preferred = parameters.get("preferred_unit")
    _reject_intensity_request(parameters, preferred)
    produced = []
    for index, source_id in enumerate(source_ids):
        cancelled()
        progress(0.2 + 0.6 * index / max(len(source_ids), 1), f"Processing {source_id}.")
        produced.append(_process_one(source_id, preferred_unit=preferred, subagent_id=subagent_id))
    progress(1.0, "Processing stored.")
    return {"datasets": produced, "data_kind": DataKind.observation.value}


def _process_one(source_id: str, *, preferred_unit: str | None, subagent_id: str) -> dict:
    with connect() as conn:
        row = get_dataset_row(conn, source_id)
        if row is None:
            raise AgentError(f"Dataset '{source_id}' is not in the catalog.", status_code=404)
        contract = DatasetContract.model_validate_json(row["contract_json"])
        raw_rows = [ObservationRow.model_validate(item) for item in list_observations(conn, source_id)]
    if contract.agent_id != "weather":
        raise AgentError("This processor only accepts Weather Agent datasets.")
    if contract.processing_level == "processed":
        return {"dataset_id": contract.dataset_id, "reused": True, "contract": contract.model_dump(mode="json")}
    target = preferred_unit or _default_unit(contract.variable)
    if contract.variable == "wind_direction":
        target = "degree"
    converted = [_convert_row(item, target) for item in raw_rows]
    quality = assess_rows(converted)
    key = _hash(f"processed|{source_id}|{target}|{PROCESSING_VERSION}")
    with connect() as conn:
        existing = dataset_by_idempotency(conn, key)
        if existing is not None:
            existing_contract = json.loads(existing["contract_json"])
            return {"dataset_id": existing["dataset_id"], "reused": True, "contract": existing_contract}
    dataset_id = _dataset_slug(contract.source.provider, contract.source.station_id or "station", contract.variable, "processed", key)
    stored_rows = [item.model_dump(mode="json") for item in converted]
    uri = _write_csv(dataset_id, stored_rows)
    built = _contract_from_rows(
        dataset_id=dataset_id,
        rows=converted,
        variable=contract.variable,
        provider=contract.source.provider,
        product=contract.source.dataset,
        source_url=contract.source.source_url,
        station_id=contract.source.station_id or "",
        station_name=contract.source.station_name,
        region_id=contract.spatial.requested_region_id or "galveston-downtown",
        requested_start=contract.temporal.requested_start,
        requested_end=contract.temporal.requested_end,
        coordinate_note=contract.spatial.coordinate_note or "",
        elevation_m=contract.vertical.station_elevation_m,
        vertical_note=contract.vertical.note,
        license_text=contract.provenance.license,
        level="processed",
        parent_dataset_id=source_id,
        raw_uri=contract.storage.uri,
        quality=quality,
        storage_uri=str(uri),
        failover_from=contract.provenance.failover_from,
        failover_reason=contract.provenance.failover_reason,
    )
    with connect() as conn:
        insert_dataset(conn, built, stored_rows, idempotency_key=key)
        _quality_row(conn, built)
    return {"dataset_id": dataset_id, "reused": False, "contract": built.model_dump(mode="json")}


def _download(provider_id, station_id, start, end, variables, *, fetcher, cancelled) -> dict:
    cancelled()
    if provider_id == "iem_asos":
        url, body, rows = fetch_reports(station_id, start, end, variables, fetcher=fetcher)
        rows = apply_calm_direction(rows)
        provider = get_provider("iem_asos")
        longitude, latitude = _first_coordinate(rows)
        return {
            "provider": "iem_asos",
            "product": "ASOS routine hourly (report_type=3)",
            "source_url": url,
            "raw_bytes": body,
            "raw_suffix": "csv",
            "rows": rows,
            "station_id": rows[0].station_id if rows else station_id,
            "station_name": "Galveston Scholes Field" if station_id.upper() in {"KGLS", "GLS"} else station_id,
            "longitude": longitude,
            "latitude": latitude,
            "elevation_m": None,
            "coordinate_note": (
                "Coordinates are the longitude and latitude columns in the IEM CSV. "
                "They are not replaced with the NOAA station-document coordinates when those differ. "
                "The point is the reporting station, not a field over downtown Galveston."
            ),
            "vertical_note": (
                "This IEM CSV does not include station elevation, vertical datum, or anemometer height. "
                "None of those were filled in."
            ),
            "license": provider.license if provider else None,
            "requested_start": iso_z(start),
            "requested_end": iso_z(end),
            "failover_from": None,
            "failover_reason": None,
        }
    if provider_id == "noaa_nws":
        url, combined, station_doc, rows = fetch_observations(
            station_id,
            start,
            end,
            fetcher=fetcher,
            cancel_check=cancelled,
        )
        rows = [row for row in rows if row.variable in variables]
        rows = apply_calm_direction(rows)
        meta_props = (station_doc or {}).get("properties") or {}
        elevation = meta_props.get("elevation") or {}
        elevation_m = elevation.get("value") if isinstance(elevation, dict) else None
        geometry = (station_doc or {}).get("geometry") or {}
        coordinates = geometry.get("coordinates") or [None, None]
        pages = combined.get("pages") or []
        features = pages[0].get("features", []) if pages else []
        note = station_location_note(station_doc, features)
        longitude, latitude = _first_coordinate(rows)
        if coordinates[0] is not None:
            longitude = float(coordinates[0])
            latitude = float(coordinates[1])
        provider = get_provider("noaa_nws")
        return {
            "provider": "noaa_nws",
            "product": "api.weather.gov station observations",
            "source_url": url,
            "raw_bytes": json.dumps(combined).encode("utf-8"),
            "raw_suffix": "json",
            "rows": rows,
            "station_id": nws_station(station_id),
            "station_name": meta_props.get("name") or (rows[0].station_name if rows else station_id),
            "longitude": longitude,
            "latitude": latitude,
            "elevation_m": elevation_m,
            "coordinate_note": note
            or "Coordinates come from the NOAA station document.",
            "vertical_note": (
                "Station elevation is the value on the NOAA station document, in metres. "
                "The observation features can carry a different elevation; that value is not copied here. "
                "The payload does not name the vertical datum, and the elevation is not an anemometer height."
                if elevation_m is not None
                else "NOAA station elevation was not present. No elevation was invented."
            ),
            "license": provider.license if provider else None,
            "requested_start": iso_z(start),
            "requested_end": iso_z(end),
            "failover_from": None,
            "failover_reason": None,
        }
    raise AgentError(f"Provider '{provider_id}' has no weather downloader.")


def _persist_bundle(bundle: dict, *, variables: list[str], region_id: str, job_key: str, level: str, preferred_unit) -> list[dict]:
    stored = []
    raw_groups: dict[str, list[ObservationRow]] = {variable: [] for variable in variables}
    for row in bundle["rows"]:
        if row.variable in raw_groups:
            raw_groups[row.variable].append(row)
    for variable, rows in raw_groups.items():
        key = _hash(f"{job_key}|{variable}|{level}")
        with connect() as conn:
            existing = dataset_by_idempotency(conn, key)
            if existing is not None:
                stored.append(
                    {
                        "dataset_id": existing["dataset_id"],
                        "reused": True,
                        "contract": json.loads(existing["contract_json"]),
                    }
                )
                continue
        quality = assess_rows(rows)
        dataset_id = _dataset_slug(bundle["provider"], bundle["station_id"], variable, level, key)
        payload = [row.model_dump(mode="json") for row in rows]
        raw_uri = _write_raw(dataset_id, bundle["raw_bytes"], bundle["raw_suffix"])
        csv_uri = _write_csv(dataset_id, payload)
        contract = _contract_from_rows(
            dataset_id=dataset_id,
            rows=rows,
            variable=variable,
            provider=bundle["provider"],
            product=bundle["product"],
            source_url=bundle["source_url"],
            station_id=str(bundle["station_id"]),
            station_name=bundle["station_name"],
            region_id=region_id,
            requested_start=bundle["requested_start"],
            requested_end=bundle["requested_end"],
            coordinate_note=bundle["coordinate_note"],
            elevation_m=bundle["elevation_m"],
            vertical_note=bundle["vertical_note"],
            license_text=bundle["license"],
            level=level,
            parent_dataset_id=None,
            raw_uri=str(raw_uri),
            quality=quality,
            storage_uri=str(csv_uri),
            failover_from=bundle.get("failover_from"),
            failover_reason=bundle.get("failover_reason"),
        )
        with connect() as conn:
            again = dataset_by_idempotency(conn, key)
            if again is not None:
                stored.append(
                    {
                        "dataset_id": again["dataset_id"],
                        "reused": True,
                        "contract": json.loads(again["contract_json"]),
                    }
                )
                continue
            insert_dataset(conn, contract, payload, idempotency_key=key)
            _quality_row(conn, contract)
        stored.append({"dataset_id": dataset_id, "reused": False, "contract": contract.model_dump(mode="json")})
    return stored


def _contract_from_rows(
    *,
    dataset_id: str,
    rows: list[ObservationRow],
    variable: str,
    provider: str,
    product: str,
    source_url: str | None,
    station_id: str,
    station_name: str | None,
    region_id: str,
    requested_start: str | None,
    requested_end: str | None,
    coordinate_note: str,
    elevation_m: float | None,
    vertical_note: str | None,
    license_text: str | None,
    level: str,
    parent_dataset_id: str | None,
    raw_uri: str | None,
    quality: dict,
    storage_uri: str,
    failover_from: str | None,
    failover_reason: str | None,
) -> DatasetContract:
    unit = rows[0].unit if rows else _default_unit(variable)
    aggregation = rows[0].aggregation if rows else (
        "hourly_accumulation" if "precipitation" in variable else "instantaneous_report"
    )
    meaning = rows[0].physical_meaning if rows else variable
    stamps = [row.observed_at for row in rows]
    longitude = rows[0].longitude if rows else None
    latitude = rows[0].latitude if rows else None
    geometry = None
    if longitude is not None and latitude is not None:
        geometry = {"type": "Point", "coordinates": [longitude, latitude]}
    methodology = RAINFALL_METHODOLOGY if "precipitation" in variable else WIND_METHODOLOGY
    if level == "processed":
        methodology += " This processed copy changes only units and quality flags. It does not create new timestamps."
    return DatasetContract(
        dataset_id=dataset_id,
        agent_id="weather",
        subagent_id="rainfall" if "precipitation" in variable else "wind",
        variable=variable,
        data_kind=DataKind.observation,
        source=SourceRef(
            provider=provider,
            dataset=product,
            source_url=source_url,
            station_id=station_id,
            station_name=station_name,
        ),
        spatial=SpatialRef(
            crs="EPSG:4326",
            geometry=geometry,
            resolution=None,
            representativeness="station_point",
            requested_region_id=region_id,
            coordinate_note=coordinate_note,
        ),
        vertical=VerticalRef(
            station_elevation_m=elevation_m,
            vertical_datum=None,
            note=vertical_note,
        ),
        temporal=TemporalRef(
            start=stamps[0] if stamps else None,
            end=stamps[-1] if stamps else None,
            resolution="1h" if aggregation == "hourly_accumulation" else "provider_report",
            requested_start=requested_start,
            requested_end=requested_end,
            alignment="provider_timestamp_not_resampled",
        ),
        measurement=MeasurementRef(
            unit=unit,
            aggregation=aggregation,
            physical_meaning=meaning,
            source_unit=unit if level == "raw" else None,
        ),
        quality=QualityRef(**quality),
        storage=StorageRef(format="csv", uri=storage_uri),
        provenance=ProvenanceRef(
            processing_version=PROCESSING_VERSION,
            license=license_text,
            methodology=methodology,
            parent_dataset_id=parent_dataset_id,
            acquired_at=iso_z(utc_now()),
            model_version=None,
            raw_uri=raw_uri,
            failover_from=failover_from,
            failover_reason=failover_reason,
        ),
        processing_level=level,
    )


def _convert_row(row: ObservationRow, target_unit: str) -> ObservationRow:
    updated = row.model_copy(deep=True)
    if updated.variable == "precipitation_hourly_accumulation":
        if updated.value is not None:
            updated.value = round_scientific(convert_length(updated.value, updated.unit, target_unit), 3)
        updated.unit = target_unit
        return updated
    if updated.variable in {"wind_speed", "wind_gust"}:
        if updated.value is not None:
            updated.value = round_scientific(convert_speed(updated.value, updated.unit, target_unit), 4)
        updated.unit = target_unit
        return updated
    if updated.variable == "wind_direction":
        if updated.value < 0 or updated.value > 360:
            updated.quality_flag = "suspect"
        return updated
    raise AgentError(f"No conversion is implemented for {updated.variable}.")


def _quality_row(conn, contract: DatasetContract) -> None:
    conn.execute(
        """
        INSERT INTO quality_assessments (assessment_id, dataset_id, status, report_json, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            "qa-" + contract.dataset_id,
            contract.dataset_id,
            contract.quality.status,
            contract.quality.model_dump_json(),
            iso_z(utc_now()),
        ),
    )


def _write_raw(dataset_id: str, body: bytes, suffix: str) -> Path:
    path = _safe_dataset_dir(dataset_id, "raw") / f"response.{suffix}"
    path.write_bytes(body)
    return path


def _write_csv(dataset_id: str, rows: list[dict]) -> Path:
    path = _safe_dataset_dir(dataset_id, "processed") / "observations.csv"
    fieldnames = [
        "station_id",
        "station_name",
        "observed_at",
        "longitude",
        "latitude",
        "variable",
        "physical_meaning",
        "value",
        "unit",
        "aggregation",
        "provider_qc",
        "quality_flag",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def _safe_dataset_dir(dataset_id: str, bucket: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9._-]{8,180}", dataset_id):
        raise AgentError("Refusing to write a dataset id with unexpected characters.")
    root = (data_root() / bucket / "weather").resolve()
    directory = (root / dataset_id).resolve()
    if root not in directory.parents:
        raise AgentError("Dataset path escaped the data directory.")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _dataset_slug(provider: str, station: str, variable: str, level: str, key: str) -> str:
    short_variable = {
        "precipitation_hourly_accumulation": "precip-hourly",
        "wind_speed": "wind-speed",
        "wind_direction": "wind-direction",
        "wind_gust": "wind-gust",
    }.get(variable, variable)
    return f"{provider}-{station}-{short_variable}-{level}-{key[:12]}"


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _default_provider(subagent_id: str) -> str:
    if subagent_id == "rainfall":
        return "iem_asos"
    return "noaa_nws"


def _default_unit(variable: str) -> str:
    if variable == "precipitation_hourly_accumulation":
        return "mm"
    if variable == "wind_direction":
        return "degree"
    return "m/s"


def _reject_intensity_request(parameters: dict, preferred_unit: str | None) -> None:
    variable = str(parameters.get("variable") or "")
    unit = preferred_unit or ""
    if variable in {"rainfall_intensity", "precipitation_intensity"} or unit in {"mm/h", "in/h"}:
        raise AgentError(
            "Rainfall intensity is not implemented. Hourly accumulation will not be relabeled as intensity."
        )


def _no_numeric_values(stored: list[dict]) -> bool:
    for item in stored:
        contract = item["contract"]
        count = contract["quality"].get("observation_count") or 0
        missing = contract["quality"].get("missing_fraction")
        if count and missing is not None and missing < 1:
            return False
    return True


def _first_coordinate(rows: list[ObservationRow]) -> tuple[float | None, float | None]:
    if not rows:
        return None, None
    return rows[0].longitude, rows[0].latitude


def _dependency_result(job: dict) -> dict:
    depends = job.get("depends_on_job_id")
    if not depends:
        raise AgentError("Processing job is missing its acquisition dependency.")
    from gdt_agents.db import find_job

    with connect() as conn:
        parent = find_job(conn, depends)
    if parent is None or parent["status"] != "completed" or not parent.get("result"):
        raise AgentError("The acquisition this processing job depends on did not complete.")
    return parent["result"]


def nws_station(station_id: str) -> str:
    if station_id.upper() == "GLS":
        return "KGLS"
    return station_id.upper()


def load_study_area() -> dict:
    return json.loads(study_area_path().read_text(encoding="utf-8"))


def discover_weather(subagent_id: str, *, live: bool) -> dict:
    subagent = get_subagent("weather", subagent_id)
    if subagent is None:
        raise AgentError(f"Unknown weather subagent '{subagent_id}'.", status_code=404)
    area = load_study_area()
    bbox = area["bbox_wgs84"]
    centroid = {
        "longitude": (bbox["west"] + bbox["east"]) / 2,
        "latitude": (bbox["south"] + bbox["north"]) / 2,
    }
    payload = {
        "subagent": subagent.model_dump(mode="json"),
        "default_station": {
            "nws_id": "KGLS",
            "iem_id": "GLS",
            "name": "Galveston Scholes Field",
            "note": (
                "The ASOS is at Scholes International Airport, west of the downtown study polygon. "
                "Observations from this station are not a downtown grid."
            ),
        },
        "study_area_centroid": centroid,
        "implemented_variables": [item.model_dump(mode="json") for item in subagent.supported_variables if item.implemented],
        "unimplemented_variables": [item.id for item in subagent.supported_variables if not item.implemented],
        "live": None,
    }
    if live and subagent.implementation_status.value == "available":
        payload["live"] = _live_station_probe(centroid)
    return payload


def _live_station_probe(centroid: dict) -> dict:
    from gdt_agents.http_client import fetch_bytes

    url = f"https://api.weather.gov/points/{centroid['latitude']},{centroid['longitude']}"
    try:
        body = fetch_bytes(url, {"Accept": "application/geo+json"}, provider="noaa_nws")
        document = json.loads(body)
    except (ProviderError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": str(exc)}
    properties = document.get("properties") or {}
    return {
        "ok": True,
        "grid": f"{properties.get('gridId')} {properties.get('gridX')},{properties.get('gridY')}",
        "observation_stations": properties.get("observationStations"),
        "forecast": properties.get("forecast"),
        "note": "Grid metadata confirms the point lookup. It is not a weather time series.",
    }
