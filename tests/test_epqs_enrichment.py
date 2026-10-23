import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def test_enrich_building_catalog_adds_lod_fields(tmp_path, monkeypatch):
    catalog = {
        "study_area": "test",
        "count": 1,
        "default_height_m": 10,
        "buildings": [
            {
                "id": "gdt-building-1",
                "osm_id": "1",
                "name": "Demo",
                "building": "commercial",
                "latitude": 29.3010,
                "longitude": -94.7960,
                "height_m": 10,
                "height_source": "estimated:default",
                "footprint_area_m2": 100,
                "footprint_wgs84": [[-94.796, 29.301], [-94.795, 29.301], [-94.795, 29.302], [-94.796, 29.301]],
                "source": "OpenStreetMap",
            }
        ],
    }
    pub = tmp_path / "buildings-catalog.json"
    pub.write_text(json.dumps(catalog), encoding="utf-8")

    import sys

    sys.path.insert(0, str(ROOT / "geospatial"))
    import export.enrich_building_catalog_lod2 as mod

    monkeypatch.setattr(mod, "CATALOG_PUBLIC", pub)
    monkeypatch.setattr(mod, "CATALOG_ASSETS", tmp_path / "assets.json")

    with patch("acquisition.epqs_elevation.query_epqs_batch", return_value=[2.5]):
        mod.main()

    enriched = json.loads(pub.read_text(encoding="utf-8"))
    b = enriched["buildings"][0]
    assert b["ground_elevation_m"] == 2.5
    assert b["lod"] == "LOD2"
    assert b["in_demo_district"] is True
    assert b["facade_material"] == "concrete"
