"""Runtime paths. PostgreSQL is not assumed to be installed."""

from __future__ import annotations

import os
from pathlib import Path

PROCESSING_VERSION = "0.1.1"
USER_AGENT = "(GDT-Research Galveston Digital Twin, local research workstation)"

# 1 international knot = 1852 m / 3600 s. ASOS wind is reported in knots.
KNOT_TO_MS = 1852 / 3600
INCH_TO_MM = 25.4
KMH_TO_MS = 1 / 3.6

# Interactive acquisitions stay bounded. Hourly ASOS for a year is enough for this milestone.
MAX_ACQUISITION_DAYS = 366


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def data_root() -> Path:
    override = os.environ.get("GDT_DATA_ROOT")
    root = Path(override) if override else repo_root() / "data"
    root.mkdir(parents=True, exist_ok=True)
    return root


def catalog_db_path() -> Path:
    directory = data_root() / "catalog"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "gdt_agents.sqlite"


def study_area_path() -> Path:
    return repo_root() / "config" / "study_area.json"
