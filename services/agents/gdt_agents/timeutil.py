"""UTC handling. Local time is a presentation concern."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from gdt_agents.errors import AgentError


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        raise AgentError("Internal timestamp was missing a timezone.")
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise AgentError(f"Could not parse timestamp '{value}'. Use an ISO-8601 UTC time.") from exc
    if parsed.tzinfo is None:
        raise AgentError(f"Timestamp '{value}' has no timezone. Use UTC, for example 2024-07-07T00:00:00Z.")
    return parsed.astimezone(timezone.utc)


def ensure_range(start: datetime, end: datetime, *, max_days: int) -> None:
    if end <= start:
        raise AgentError("Time range end must be after the start.")
    if end - start > timedelta(days=max_days):
        raise AgentError(
            f"Time range exceeds {max_days} days. Split the request so the acquisition stays bounded."
        )
