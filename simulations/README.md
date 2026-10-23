# Future simulation modules

Simulation domains (flooding, UAV/UGV, traffic, wireless, multi-agent, etc.) are **not implemented** in the current milestone.

The visualization platform in `apps/web` is intended to expose stable hooks later:

- Geographic object IDs from PostGIS
- Scene layer visibility
- Custom entity placement API
- Time-varying result overlays

Keep simulation logic out of the Cesium renderer; integrate via backend services and typed client adapters.
