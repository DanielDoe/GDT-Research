"""Coordinate helpers.

Weather acquisitions stay in EPSG:4326. A transform is available for checks
and is recorded; station observations are not silently reprojected into a grid.
"""

from __future__ import annotations

from gdt_agents.errors import AgentError


def transform_point(longitude: float, latitude: float, source_crs: str, target_crs: str) -> tuple[float, float]:
    if source_crs == target_crs:
        return longitude, latitude
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise AgentError(
            "pyproj is not installed, so this CRS transformation was not performed."
        ) from exc
    transformer = Transformer.from_crs(source_crs, target_crs, always_xy=True)
    x, y = transformer.transform(longitude, latitude)
    return float(x), float(y)
