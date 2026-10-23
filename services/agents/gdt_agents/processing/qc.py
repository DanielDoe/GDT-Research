"""Range checks. Suspect values are kept and flagged, not deleted or replaced."""

from __future__ import annotations

from gdt_agents.contracts import ObservationRow

# Hourly gauge amounts above 250 mm are outside the range expected at this ASOS.
# They are retained so a researcher can see the provider value.
HOURLY_PRECIP_SUSPECT_MM = 250.0
WIND_SUSPECT_MS = 90.0


def assess_rows(rows: list[ObservationRow]) -> dict:
    if not rows:
        return {
            "status": "failed",
            "missing_fraction": None,
            "trace_count": 0,
            "suspect_count": 0,
            "observation_count": 0,
            "notes": ["The provider returned no observations for this station and interval."],
        }
    missing = 0
    traces = 0
    suspects = 0
    for row in rows:
        if row.quality_flag == "trace":
            traces += 1
            continue
        if row.value is None:
            missing += 1
            continue
        if _is_suspect(row):
            suspects += 1
            if row.quality_flag is None:
                row.quality_flag = "suspect"
    missing_fraction = missing / len(rows)
    notes: list[str] = []
    if traces:
        notes.append(
            f"{traces} report(s) were precipitation traces. Trace is not stored as a depth."
        )
    if suspects:
        notes.append(
            f"{suspects} value(s) exceeded the range check and were kept with quality_flag=suspect."
        )
    notes.append(
        "A single station does not describe conditions across Galveston or the downtown study area."
    )
    if missing_fraction > 0.5:
        status = "incomplete"
        notes.append("More than half of the numeric values are missing.")
    elif not rows:
        status = "failed"
    else:
        status = "provider_reported"
    return {
        "status": status,
        "missing_fraction": missing_fraction,
        "trace_count": traces,
        "suspect_count": suspects,
        "observation_count": len(rows),
        "notes": notes,
        "uncertainty": (
            "No independent reference series was compared. "
            "ASOS hourly precipitation is reported to 0.01 inch; converted millimetres are not more precise."
        ),
    }


def _is_suspect(row: ObservationRow) -> bool:
    if row.value is None:
        return False
    if row.physical_meaning == "precipitation_hourly_accumulation" and row.unit == "mm":
        return row.value > HOURLY_PRECIP_SUSPECT_MM
    if row.physical_meaning in {"wind_speed", "wind_gust"} and row.unit == "m/s":
        return row.value > WIND_SUSPECT_MS
    if row.physical_meaning == "wind_direction":
        return row.value < 0 or row.value > 360
    return False
