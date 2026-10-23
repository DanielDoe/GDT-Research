import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "study_area.json"


def test_study_area_bbox_is_valid() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    bb = cfg["bbox_wgs84"]
    assert bb["west"] < bb["east"]
    assert bb["south"] < bb["north"]
    assert 29.0 < bb["south"] < 30.0
    assert -95.0 < bb["west"] < -94.0


def test_camera_presets_exist() -> None:
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert "study_area" in cfg["camera_presets"]
    assert "downtown" in cfg["camera_presets"]
