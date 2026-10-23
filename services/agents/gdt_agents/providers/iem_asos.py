"""Iowa Environmental Mesonet redistribution of NOAA ASOS reports."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlencode

from gdt_agents.contracts import ObservationRow
from gdt_agents.errors import ProviderError
from gdt_agents.http_client import fetch_bytes
from gdt_agents.timeutil import iso_z

IEM_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
VARIABLE_FIELDS = {
    "precipitation_hourly_accumulation": "p01i",
    "wind_speed": "sknt",
    "wind_direction": "drct",
    "wind_gust": "gust",
}
FIELD_META = {
    "p01i": ("precipitation_hourly_accumulation", "in", "hourly_accumulation"),
    "sknt": ("wind_speed", "kt", "instantaneous_report"),
    "drct": ("wind_direction", "degree", "instantaneous_report"),
    "gust": ("wind_gust", "kt", "instantaneous_report"),
}


def station_iem_id(station_id: str) -> str:
    token = station_id.strip().upper()
    if token == "KGLS":
        return "GLS"
    return token


def build_url(station_id: str, start: datetime, end: datetime, variables: list[str]) -> str:
    fields = []
    for variable in variables:
        field = VARIABLE_FIELDS.get(variable)
        if field is None:
            raise ProviderError(
                f"IEM ASOS has no implemented field for '{variable}'.",
                provider="iem_asos",
                retryable=False,
                status_code=400,
            )
        fields.append(field)
    # IEM day bounds are inclusive calendar dates in the requested timezone.
    # Records are filtered to the requested instant range after download.
    pairs: list[tuple[str, str]] = [("station", station_iem_id(station_id))]
    for field in fields:
        pairs.append(("data", field))
    pairs.extend(
        [
            ("year1", str(start.year)),
            ("month1", str(start.month)),
            ("day1", str(start.day)),
            ("year2", str(end.year)),
            ("month2", str(end.month)),
            ("day2", str(end.day)),
            ("tz", "Etc/UTC"),
            ("format", "onlycomma"),
            ("latlon", "yes"),
            ("missing", "M"),
            ("trace", "T"),
            ("direct", "no"),
            ("report_type", "3"),
        ]
    )
    return f"{IEM_URL}?{urlencode(pairs)}"


def fetch_reports(
    station_id: str,
    start: datetime,
    end: datetime,
    variables: list[str],
    *,
    fetcher=None,
) -> tuple[str, bytes, list[ObservationRow]]:
    url = build_url(station_id, start, end, variables)
    if fetcher is None:
        body = fetch_bytes(url, {"Accept": "text/csv"}, provider="iem_asos")
    else:
        body = fetcher(url)
    rows = parse_asos_csv(body, variables=set(variables), start=start, end=end)
    return url, body, rows


def parse_asos_csv(
    body: bytes,
    *,
    variables: set[str],
    start: datetime,
    end: datetime,
) -> list[ObservationRow]:
    text = body.decode("utf-8", errors="replace")
    if text.lstrip().startswith("<"):
        raise ProviderError(
            "IEM returned a document that is not the ASOS CSV.",
            provider="iem_asos",
            retryable=True,
        )
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("station,valid"):
        raise ProviderError(
            "IEM response did not contain the ASOS header.",
            provider="iem_asos",
            retryable=True,
        )
    header = lines[0].split(",")
    index = {name: position for position, name in enumerate(header)}
    required = {"station", "valid", "lon", "lat"}
    if not required.issubset(index):
        raise ProviderError("IEM CSV is missing station coordinates or time.", provider="iem_asos")
    seen: set[tuple] = set()
    rows: list[ObservationRow] = []
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) < len(header):
            continue
        stamp = _parse_valid(parts[index["valid"]])
        if stamp < start or stamp >= end:
            continue
        try:
            longitude = float(parts[index["lon"]])
            latitude = float(parts[index["lat"]])
        except ValueError as exc:
            raise ProviderError("IEM CSV contained a non-numeric coordinate.", provider="iem_asos") from exc
        station = parts[index["station"]]
        for field, (variable, unit, aggregation) in FIELD_META.items():
            if variable not in variables or field not in index:
                continue
            token = parts[index[field]].strip()
            identity = (station, iso_z(stamp), variable, token)
            if identity in seen:
                continue
            seen.add(identity)
            value, flag = _parse_token(variable, token)
            rows.append(
                ObservationRow(
                    station_id=station,
                    station_name="Galveston Scholes Field",
                    longitude=longitude,
                    latitude=latitude,
                    observed_at=iso_z(stamp),
                    variable=variable,
                    physical_meaning=variable,
                    value=value,
                    unit=unit,
                    aggregation=aggregation,
                    quality_flag=flag,
                )
            )
    rows.sort(key=lambda row: (row.observed_at, row.variable))
    return rows


def _parse_valid(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError as exc:
        raise ProviderError(f"IEM timestamp '{value}' was not understood.", provider="iem_asos") from exc
    return parsed.replace(tzinfo=timezone.utc)


def _parse_token(variable: str, token: str) -> tuple[float | None, str | None]:
    if token == "" or token == "M":
        return None, "missing"
    if token == "T":
        if variable != "precipitation_hourly_accumulation":
            return None, "missing"
        return None, "trace"
    try:
        value = float(token)
    except ValueError as exc:
        raise ProviderError(f"IEM value '{token}' is not numeric.", provider="iem_asos") from exc
    if variable == "wind_direction" and value == 0.0:
        # Direction is resolved after speed is known. Zero alone may be calm or north.
        return 0.0, None
    return value, None


def apply_calm_direction(rows: list[ObservationRow]) -> list[ObservationRow]:
    """Calm ASOS reports use direction 0 with speed 0. That direction is undefined, not north."""
    speed_by_time: dict[str, float | None] = {}
    for row in rows:
        if row.variable == "wind_speed":
            speed_by_time[row.observed_at] = row.value
    for row in rows:
        if row.variable != "wind_direction" or row.value != 0.0:
            continue
        speed = speed_by_time.get(row.observed_at)
        if speed == 0.0:
            row.value = None
            row.quality_flag = "calm"
    return rows
