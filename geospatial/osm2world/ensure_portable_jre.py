#!/usr/bin/env python3
"""Download a portable Temurin 17 JRE for OSM2World (no system Java required)."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen, urlretrieve

ROOT = Path(__file__).resolve().parents[2]
JRE = ROOT / "geospatial" / "osm2world" / "jre"
ZIP_PATH = ROOT / "geospatial" / "osm2world" / "jre.zip"


def main() -> None:
    if (JRE / "bin" / "java.exe").exists():
        print(f"Portable JRE already present: {JRE / 'bin' / 'java.exe'}")
        return

    api = (
        "https://api.adoptium.net/v3/assets/latest/17/hotspot"
        "?architecture=x64&image_type=jre&os=windows&vendor=eclipse"
    )
    assets = json.load(urlopen(Request(api, headers={"User-Agent": "GDT-Research"})))
    url = assets[0]["binary"]["package"]["link"]
    print(f"Downloading portable JRE from {url}")
    urlretrieve(url, ZIP_PATH)

    tmp = JRE.parent / "_jre_extract"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(tmp)
    child = next(p for p in tmp.iterdir() if p.is_dir())
    if JRE.exists():
        shutil.rmtree(JRE)
    shutil.move(str(child), str(JRE))
    shutil.rmtree(tmp)
    ZIP_PATH.unlink(missing_ok=True)
    print(f"Installed {JRE / 'bin' / 'java.exe'}")


if __name__ == "__main__":
    main()
