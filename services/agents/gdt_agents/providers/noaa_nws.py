"""NOAA api.weather.gov station observations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from gdt_agents.contracts import ObservationRow
from gdt_agents.errors import ProviderError
from gdt_agents.http_client import fetch_bytes
from gdt_agents.timeutil import iso_z

NWS_QUANTITIES = {
    "windSpeed": ("wind_speed", "instantaneous_report"),
    "windDirection": ("wind_direction", "instantaneous_report"),
    "windGust": ("wind_gust", "instantaneous_report"),
    "precipitationLastHour": ("precipitation_hourly_accumulation", "hourly_accumulation"),
}
UNIT_CODES = {
    "wmoUnit:km_h-1": "km/h",
    "wmoUnit:m_s-1": "m/s",
    "wmoUnit:kt": "kt",
    "wmoUnit:degree_(angle)": "degree",
    "wmoUnit:mm": "mm",
    "wmoUnit:in": "in",
}


def nws_station_id(station_id: str) -> str:
    token = station_id.strip().upper()
    if token == "GLS":
        return "KGLS"
    return token


def fetch_observations(
    station_id: str,
    start: datetime,
    end: datetime,
    *,
    fetcher=None,
    cancel_check=None,
) -> tuple[str, dict, dict, list[ObservationRow]]:
    station = nws_station_id(station_id)
    collection_url = (
        "https://api.weather.gov/stations/"
        f"{station}/observations?start={iso_z(start)}&end={iso_z(end)}&limit=500"
    )
    pages: list[dict] = []
    url: str | None = collection_url
    page_count = 0
    while url:
        if cancel_check:
            cancel_check()
        page_count += 1
        if page_count > 20:
            raise ProviderError(
                "NOAA NWS pagination exceeded 20 pages. Narrow the time range.",
                provider="noaa_nws",
                retryable=False,
                status_code=400,
            )
        payload = _get_json(url, fetcher)
        pages.append(payload)
        url = (payload.get("pagination") or {}).get("next")
    station_url = f"https://api.weather.gov/stations/{station}"
    station_doc = _get_json(station_url, fetcher)
    combined = {"type": "FeatureCollection", "pages": pages, "station": station_doc}
    features: list[dict] = []
    for page in pages:
        features.extend(page.get("features") or [])
    rows = parse_observations(features, station_doc, start=start, end=end)
    return collection_url, combined, station_doc, rows


def fetch_recent(
    station_id: str,
    lookback_hours: int,
    *,
    fetcher=None,
    cancel_check=None,
    now: datetime | None = None,
) -> tuple[str, dict, dict, list[ObservationRow], datetime, datetime]:
    if lookback_hours < 1 or lookback_hours > 24 * 14:
        raise ProviderError(
            "NOAA NWS lookback must be between 1 hour and 14 days.",
            provider="noaa_nws",
            retryable=False,
            status_code=400,
        )
    end = now or datetime.now(timezone.utc)
    start = end - timedelta(hours=lookback_hours)
    url, combined, station_doc, rows = fetch_observations(
        station_id,
        start,
        end,
        fetcher=fetcher,
        cancel_check=cancel_check,
    )
    return url, combined, station_doc, rows, start, end


def parse_observations(
    features: list[dict],
    station_doc: dict | None,
    *,
    start: datetime,
    end: datetime,
) -> list[ObservationRow]:
    meta = _station_metadata(station_doc)
    rows: list[ObservationRow] = []
    for feature in features:
        properties = feature.get("properties") or {}
        stamp = properties.get("timestamp")
        if not stamp:
            continue
        observed = _parse_stamp(stamp)
        if observed < start or observed >= end:
            continue
        reported_geometry = feature.get("geometry")
        longitude, latitude, location_note = _location(meta, reported_geometry)
        station_id = properties.get("stationId") or meta.get("station_id") or "KGLS"
        station_name = properties.get("stationName") or meta.get("name")
        degraded = location_note is not None
        for key, (variable, aggregation) in NWS_QUANTITIES.items():
            quantity = properties.get(key)
            value, unit, qc, flag = _quantity(quantity)
            if variable == "wind_direction" and value == 0:
                speed = _quantity(properties.get("windSpeed"))[0]
                if speed == 0:
                    value = None
                    flag = "calm"
            if degraded and flag is None and value is None:
                flag = "missing"
            rows.append(
                ObservationRow(
                    station_id=station_id,
                    station_name=station_name,
                    longitude=longitude,
                    latitude=latitude,
                    observed_at=iso_z(observed),
                    variable=variable,
                    physical_meaning=variable,
                    value=value,
                    unit=unit or _default_unit(variable),
                    aggregation=aggregation,
                    provider_qc=qc,
                    quality_flag=flag,
                )
            )
    rows.sort(key=lambda row: (row.observed_at, row.variable))
    return rows


def station_location_note(station_doc: dict | None, features: list[dict]) -> str | None:
    meta = _station_metadata(station_doc)
    if meta.get("longitude") is None:
        return (
            "NOAA station metadata was unavailable. Observation geometry from api.weather.gov "
            "is often rounded to 0.1 degree and is not a survey location."
        )
    for feature in features:
        geometry = feature.get("geometry") or {}
        coords = geometry.get("coordinates")
        if not coords:
            continue
        if abs(coords[0] - meta["longitude"]) > 0.01 or abs(coords[1] - meta["latitude"]) > 0.01:
            return (
                "The observation GeoJSON point was rounded (often to 0.1 degree) and was not used. "
                f"Coordinates come from the NWS station document "
                f"({meta['longitude']}, {meta['latitude']})."
            )
    return None


def _station_metadata(station_doc: dict | None) -> dict[str, Any]:
    if not station_doc:
        return {}
    geometry = station_doc.get("geometry") or {}
    coordinates = geometry.get("coordinates") or [None, None]
    properties = station_doc.get("properties") or {}
    elevation = properties.get("elevation") or {}
    return {
        "station_id": properties.get("stationIdentifier"),
        "name": properties.get("name"),
        "longitude": coordinates[0],
        "latitude": coordinates[1],
        "elevation_m": elevation.get("value") if isinstance(elevation, dict) else None,
        "observation_elevation_conflict": True,
    }


def _location(meta: dict, reported_geometry: dict | None) -> tuple[float, float, str | None]:
    if meta.get("longitude") is not None and meta.get("latitude") is not None:
        note = None
        coords = (reported_geometry or {}).get("coordinates")
        if coords and (abs(coords[0] - meta["longitude"]) > 0.01 or abs(coords[1] - meta["latitude"]) > 0.01):
            note = "rounded_observation_geometry_ignored"
        return float(meta["longitude"]), float(meta["latitude"]), note
    coords = (reported_geometry or {}).get("coordinates")
    if not coords:
        raise ProviderError(
            "NOAA NWS did not provide station coordinates.",
            provider="noaa_nws",
            retryable=True,
        )
    return float(coords[0]), float(coords[1]), "station_metadata_missing"


def _quantity(quantity: Any) -> tuple[float | None, str | None, str | None, str | None]:
    if quantity is None:
        return None, None, None, "missing"
    if not isinstance(quantity, dict):
        return None, None, None, "missing"
    unit = UNIT_CODES.get(quantity.get("unitCode") or "", quantity.get("unitCode"))
    qc = quantity.get("qualityControl")
    value = quantity.get("value")
    if value is None:
        return None, unit, qc, "missing"
    return float(value), unit, qc, None


def _default_unit(variable: str) -> str:
    if variable == "wind_direction":
        return "degree"
    if variable == "precipitation_hourly_accumulation":
        return "mm"
    return "m/s"


def _parse_stamp(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _get_json(url: str, fetcher) -> dict:
    if fetcher is None:
        body = fetch_bytes(url, {"Accept": "application/geo+json"}, provider="noaa_nws")
    else:
        body = fetcher(url)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ProviderError("NOAA NWS returned a document that is not JSON.", provider="noaa_nws") from exc
    if isinstance(payload, dict) and payload.get("status") and payload.get("detail") and "features" not in payload:
        raise ProviderError(
            f"NOAA NWS error: {payload.get('detail')}",
            provider="noaa_nws",
            retryable=False,
        )
    return payload
