#!/usr/bin/env python3
"""Download and extract OSM2World 0.4.0 binary distribution."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "geospatial" / "osm2world" / "bin"
ZIP_PATH = ROOT / "geospatial" / "osm2world" / "OSM2World-0.4.0-bin.zip"
URL = "https://osm2world.org/download/files/0.4.0/OSM2World-0.4.0-bin.zip"


def find_launcher(extracted_root: Path) -> Path:
    for candidate in extracted_root.rglob("OSM2World.jar"):
        return candidate
    for candidate in extracted_root.rglob("OSM2World*.bat"):
        return candidate
    raise FileNotFoundError("OSM2World launcher not found in archive")


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    marker = DEST / ".installed"
    if marker.exists():
        print(f"OSM2World already installed under {DEST}")
        return

    if not ZIP_PATH.exists() or ZIP_PATH.stat().st_size < 10_000_000:
        print(f"Downloading {URL} (this is ~430 MB)...")
        urlretrieve(URL, ZIP_PATH)

    tmp = DEST / "_extract"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(tmp)

    # Flatten single top-level folder if present
    children = [p for p in tmp.iterdir() if p.name != "__MACOSX"]
    extracted_root = children[0] if len(children) == 1 and children[0].is_dir() else tmp
    for item in extracted_root.iterdir():
        target = DEST / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(item), str(target))

    shutil.rmtree(tmp, ignore_errors=True)
    launcher = find_launcher(DEST)
    marker.write_text(str(launcher), encoding="utf-8")
    print(f"Installed OSM2World launcher: {launcher}")


if __name__ == "__main__":
    main()
