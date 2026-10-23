"""Unit conversions with exact factors. Missing values stay missing."""

from __future__ import annotations

from decimal import Decimal

from gdt_agents.errors import AgentError

# Exact conversion factors. Do not route these through binary floats first.
INCH_TO_MM = Decimal("25.4")
KNOT_TO_MS = Decimal(1852) / Decimal(3600)
KMH_TO_MS = Decimal(1) / Decimal("3.6")


def _to_decimal(value: float) -> Decimal:
    return Decimal(str(value))


def inches_to_mm(value: float) -> float:
    return float(_to_decimal(value) * INCH_TO_MM)


def knots_to_ms(value: float) -> float:
    return float(_to_decimal(value) * KNOT_TO_MS)


def kmh_to_ms(value: float) -> float:
    return float(_to_decimal(value) * KMH_TO_MS)


def convert_length(value: float, source_unit: str, target_unit: str) -> float:
    if source_unit == target_unit:
        return value
    if source_unit == "in" and target_unit == "mm":
        return inches_to_mm(value)
    if source_unit == "mm" and target_unit == "in":
        return float(_to_decimal(value) / INCH_TO_MM)
    raise AgentError(f"Cannot convert precipitation from {source_unit} to {target_unit}.")


def convert_speed(value: float, source_unit: str, target_unit: str) -> float:
    if source_unit == target_unit:
        return value
    metres = value
    if source_unit == "kt":
        metres = knots_to_ms(value)
    elif source_unit == "km/h":
        metres = kmh_to_ms(value)
    elif source_unit == "m/s":
        metres = value
    else:
        raise AgentError(f"Unsupported wind speed unit '{source_unit}'.")
    if target_unit == "m/s":
        return metres
    if target_unit == "kt":
        return float(Decimal(str(metres)) / KNOT_TO_MS)
    if target_unit == "km/h":
        return float(Decimal(str(metres)) / KMH_TO_MS)
    raise AgentError(f"Unsupported wind speed target '{target_unit}'.")


def round_scientific(value: float | None, places: int) -> float | None:
    if value is None:
        return None
    quant = Decimal("1").scaleb(-places)
    return float(_to_decimal(value).quantize(quant))
