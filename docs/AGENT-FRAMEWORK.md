# Agent framework

The Cesium viewer is still the Map tab. The Agents tab configures research families and calls the FastAPI catalog.

## What runs

- Weather rainfall and wind acquire NOAA observations. Historical hourly accumulation and wind come from Iowa Environmental Mesonet ASOS routine reports (`report_type=3`). Recent station observations come from `api.weather.gov`.
- Hourly precipitation is stored as accumulation. Trace is a flag, not a depth. Missing values stay missing. A station point is not expanded across downtown.
- The other 16 families, and the remaining weather variables, are registry entries. Acquire requests for them return an error and do not invent rows.
- Jobs are stored in SQLite (`data/catalog/gdt_agents.sqlite`) and drained by one worker thread. PostGIS DDL is in `database/migrations/001_agent_framework.sql` for a server that has PostGIS. It is not applied automatically.
- Scenarios saved from the Agents tab are visualization manifests. No hydrodynamic, traffic, or vehicle model is launched.

## API

`GET /api/v1/agents` lists families. `POST /api/v1/agents/operations` with `workflow: acquire_and_process` queues acquisition and processing. Dataset contracts include source, time, unit, quality, and provenance.
