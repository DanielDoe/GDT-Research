"""Catalog assistant.

Questions are routed to registered catalog tools. No language model is called,
and nothing here starts a job or writes a measurement.
"""

from __future__ import annotations

from gdt_agents.catalog_ops import flood_gap_report, search_datasets


def ask(question: str) -> dict:
    text = " ".join(question.split())
    if not text:
        raise ValueError("Question is empty.")
    lowered = text.lower()
    tools: list[str] = []
    citations: list[dict] = []
    if "flood" in lowered:
        tools.append("flood_gap_report")
        report = flood_gap_report()
        lines = [report["statement"]]
        for item in report["requirements"]:
            lines.append(f"{item['role']}: {item['status']}. {item['detail']}")
        answer = " ".join(lines)
    elif any(word in lowered for word in ("elevation", "lidar", "terrain", "bathymetry")):
        tools.append("search_datasets")
        found = search_datasets(agent_id="geospatial_survey")
        citations = [_cite(item) for item in found]
        if found:
            answer = "Elevation datasets currently in the catalog: " + ", ".join(
                item["dataset_id"] for item in found
            )
        else:
            answer = (
                "No elevation dataset is in the catalog. "
                "The Geospatial Survey Agent is registered but has no connector, so no coverage ranking was invented."
            )
    elif any(word in lowered for word in ("rainfall", "precipitation", "rain")):
        tools.append("search_datasets")
        found = search_datasets(agent_id="weather", subagent_id="rainfall")
        citations = [_cite(item) for item in found]
        if not found:
            answer = (
                "No rainfall dataset is in the catalog yet. "
                "The Rainfall subagent can request NOAA ASOS hourly accumulation for Galveston Scholes Field "
                "(IEM station GLS, or NWS station KGLS when that feed contains precipitation)."
            )
        else:
            parts = []
            for item in found:
                parts.append(
                    f"{item['dataset_id']} ({item['data_kind']}, {item['measurement']['unit']}, "
                    f"{item['source']['provider']}, quality {item['quality']['status']})"
                )
            answer = "Rainfall datasets in the catalog: " + "; ".join(parts) + "."
    elif "wind" in lowered and any(word in lowered for word in ("uav", "combine", "scenario")):
        tools.append("search_datasets")
        found = search_datasets(agent_id="weather", subagent_id="wind", variable="wind_speed")
        citations = [_cite(item) for item in found]
        answer = (
            "Wind observations can be added to a visualization scenario beside other station series. "
            "They cannot yet be written as a UAV simulator input, and a station does not describe wind "
            "over the whole study area. No spatial wind field was created."
        )
        if found:
            answer += " Catalogued wind-speed datasets: " + ", ".join(item["dataset_id"] for item in found) + "."
        else:
            answer += " No wind-speed dataset is in the catalog yet."
    elif "limitation" in lowered or "limitations" in lowered:
        tools.append("search_datasets")
        found = search_datasets(agent_id="weather")
        citations = [_cite(item) for item in found]
        answer = (
            "Station series are observations at the reporting site only. "
            "Timestamps are not interpolated. Trace precipitation is not a depth. "
            "Hourly accumulation is not intensity. "
            "The viewer marker height is not an anemometer height. "
            "No numerical flood, traffic, or vehicle model is configured, and results are not operational guidance."
        )
    else:
        answer = (
            "I can answer from the catalog tools only: which rainfall or wind datasets are stored, "
            "whether an elevation dataset exists, what a flood experiment is missing, and the limits of a station series. "
            "No language model is configured, and I will not guess a measurement."
        )
    return {
        "question": text,
        "answer": answer,
        "tools_used": tools,
        "citations": citations,
        "model": None,
        "method": "deterministic_catalog_tools",
        "jobs_started": False,
    }


def _cite(contract: dict) -> dict:
    source = contract.get("source") or {}
    return {
        "dataset_id": contract.get("dataset_id"),
        "provider": source.get("provider"),
        "dataset": source.get("dataset"),
        "source_url": source.get("source_url"),
        "data_kind": contract.get("data_kind"),
        "license": (contract.get("provenance") or {}).get("license"),
    }
