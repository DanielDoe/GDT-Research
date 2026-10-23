"""Static agent catalog.

Domain families other than Weather are registered so researchers can see the
planned platform. They have no connectors and cannot return data.
"""

from __future__ import annotations

from gdt_agents.contracts import (
    AgentDefinition,
    ImplementationStatus,
    ProviderDefinition,
    SubagentDefinition,
    VariableSpec,
)

_UNAVAILABLE = (
    "Not implemented. This registry entry does not acquire, simulate, or invent data."
)


def _planned(parent: str, subagent_id: str, name: str, description: str) -> SubagentDefinition:
    return SubagentDefinition(
        id=subagent_id,
        name=name,
        parent_agent_id=parent,
        description=description,
        implementation_status=ImplementationStatus.unavailable,
        unavailable_reason=_UNAVAILABLE,
        geographic_coverage="Not available until a connector is implemented.",
        temporal_coverage="Not available until a connector is implemented.",
    )


def _family(
    agent_id: str,
    name: str,
    description: str,
    subagents: list[tuple[str, str, str]],
) -> AgentDefinition:
    return AgentDefinition(
        id=agent_id,
        name=name,
        category="domain",
        description=description,
        implementation_status="planned",
        subagents=[_planned(agent_id, sid, title, text) for sid, title, text in subagents],
        simulation_outputs=[],
    )


WEATHER_RAINFALL = SubagentDefinition(
    id="rainfall",
    name="Rainfall",
    parent_agent_id="weather",
    description=(
        "Station precipitation from routine ASOS reports. The implemented variable is "
        "hourly accumulation, not rainfall intensity and not a spatial rainfall field."
    ),
    implementation_status=ImplementationStatus.available,
    supported_variables=[
        VariableSpec(
            id="precipitation_hourly_accumulation",
            name="Hourly precipitation accumulation",
            physical_meaning="precipitation_hourly_accumulation",
            implemented=True,
            units=["mm", "in"],
            aggregation="hourly_accumulation",
            note="ASOS p01i is the accumulation over the hour ending at the report time.",
        ),
        VariableSpec(
            id="rainfall_intensity",
            name="Rainfall intensity",
            physical_meaning="precipitation_intensity",
            implemented=False,
            units=["mm/h"],
            note="Not derived in this version, so accumulation is not relabeled as intensity.",
        ),
        VariableSpec(
            id="daily_precipitation",
            name="Daily precipitation",
            physical_meaning="precipitation_daily_accumulation",
            implemented=False,
            units=["mm"],
            note="Daily totals are not summed here because sub-hourly reports would double-count p01i.",
        ),
        VariableSpec(
            id="radar_estimated_precipitation",
            name="Radar-estimated precipitation",
            physical_meaning="radar_precipitation_estimate",
            implemented=False,
            units=["mm"],
            note="MRMS is not connected. Radar estimates will not be substituted for gauge reports.",
        ),
        VariableSpec(
            id="forecast_precipitation",
            name="Forecast precipitation",
            physical_meaning="forecast_precipitation",
            implemented=False,
            units=["mm"],
            note="Forecast grids are a different data kind and are not mixed into this observation series.",
        ),
    ],
    data_providers=["iem_asos", "noaa_nws"],
    required_parameters=["region_id", "time_range or an explicit historical preset", "provider"],
    output_schemas=["gdt.timeseries.station.v1", "gdt.cesium.point.v1"],
    geographic_coverage=(
        "Galveston Scholes Field ASOS (KGLS / IEM GLS), a point outside the downtown study polygon."
    ),
    temporal_coverage=(
        "IEM serves historical routine hourly reports. The NOAA NWS API serves recent observations "
        "and often omits precipitation for this station."
    ),
    units=["mm", "in"],
    processing_requirements=[
        "Preserve trace as a flag rather than a depth.",
        "Do not fill missing hours with zero.",
        "Do not resample onto clock-hour timestamps.",
    ],
    simulation_compatibility=[
        "Single-station hourly accumulation can be inspected or used later as a comparison series.",
        "It is not a gridded hydrologic forcing product.",
        "No hydrodynamic model is connected.",
    ],
)

WEATHER_WIND = SubagentDefinition(
    id="wind",
    name="Wind",
    parent_agent_id="weather",
    description=(
        "Station wind speed, direction, and gust. Direction is the meteorological direction "
        "the wind is coming from. This is not a vertical wind profile."
    ),
    implementation_status=ImplementationStatus.available,
    supported_variables=[
        VariableSpec(
            id="wind_speed",
            name="Wind speed",
            physical_meaning="wind_speed",
            implemented=True,
            units=["m/s", "kt", "km/h"],
            aggregation="instantaneous_report",
        ),
        VariableSpec(
            id="wind_direction",
            name="Wind direction",
            physical_meaning="wind_direction",
            implemented=True,
            units=["degree"],
            aggregation="instantaneous_report",
            note="Calm reports store a null direction. Zero degrees with nonzero speed means north.",
        ),
        VariableSpec(
            id="wind_gust",
            name="Wind gust",
            physical_meaning="wind_gust",
            implemented=True,
            units=["m/s", "kt", "km/h"],
            aggregation="instantaneous_report",
            note="Missing gusts stay missing. They are not copied from the sustained wind.",
        ),
        VariableSpec(
            id="vertical_wind_profile",
            name="Vertical wind profile",
            physical_meaning="vertical_wind_profile",
            implemented=False,
            units=["m/s"],
            note="ASOS and the NWS station observation do not provide a profile.",
        ),
    ],
    data_providers=["noaa_nws", "iem_asos"],
    required_parameters=["region_id", "time_range or lookback_hours", "provider"],
    output_schemas=["gdt.timeseries.station.v1", "gdt.cesium.point.v1"],
    geographic_coverage=(
        "Galveston Scholes Field ASOS (KGLS / IEM GLS), a point outside the downtown study polygon."
    ),
    temporal_coverage=(
        "NOAA NWS API: recent observations. IEM ASOS: historical routine hourly reports."
    ),
    units=["m/s", "kt", "degree"],
    processing_requirements=[
        "Convert knots or kilometres per hour to metres per second with exact factors.",
        "Do not interpolate between reports.",
        "Do not treat the display height in Cesium as an anemometer height.",
    ],
    simulation_compatibility=[
        "Suitable as a station time series for later UAV wind-input work.",
        "This version does not write a UAV simulator file or a spatial wind field.",
    ],
)


def _weather_unavailable(subagent_id: str, name: str, description: str) -> SubagentDefinition:
    return SubagentDefinition(
        id=subagent_id,
        name=name,
        parent_agent_id="weather",
        description=description,
        implementation_status=ImplementationStatus.unavailable,
        unavailable_reason=(
            "Registered on the Weather Agent. No processor is implemented yet, so this "
            "subagent will not estimate values from the rainfall or wind series."
        ),
        geographic_coverage="Galveston area, once a processor is implemented.",
        temporal_coverage="Not available.",
    )


WEATHER = AgentDefinition(
    id="weather",
    name="Weather and Atmospheric Intelligence",
    category="domain",
    description=(
        "Acquires and standardizes Galveston station meteorology. Rainfall and wind read "
        "public NOAA ASOS observations. Other weather variables are registered only."
    ),
    implementation_status="partial",
    subagents=[
        WEATHER_RAINFALL,
        WEATHER_WIND,
        _weather_unavailable("temperature", "Temperature", "Air temperature, extremes, and dew point."),
        _weather_unavailable("humidity", "Humidity", "Relative humidity and moisture conditions."),
        _weather_unavailable(
            "atmospheric_pressure",
            "Atmospheric Pressure",
            "Surface pressure, sea-level pressure, and pressure tendency.",
        ),
        _weather_unavailable(
            "solar_radiation",
            "Solar and Radiation",
            "Irradiance, sunshine duration, cloud cover, and daylight.",
        ),
        _weather_unavailable(
            "visibility_severe",
            "Visibility and Severe Weather",
            "Visibility, fog, thunderstorms, and tropical-cyclone advisories.",
        ),
    ],
    providers=["noaa_nws", "iem_asos"],
    simulation_outputs=[
        "Station time series for rainfall accumulation and wind.",
        "Cesium point marker for the reporting station.",
    ],
    required_credentials=[],
)


AGENTS: list[AgentDefinition] = [
    WEATHER,
    _family(
        "satellite",
        "Satellite and Remote Sensing",
        "Planned optical, multispectral, thermal, SAR, land-cover, and change-detection products. Commercial map basemaps are not scientific satellite products.",
        [
            ("optical", "Optical Imagery", "Landsat, Sentinel-2, surface reflectance, and composites."),
            ("multispectral", "Multispectral Analysis", "Spectral indices such as NDVI, NDWI, and NDBI."),
            ("thermal", "Thermal Analysis", "Land surface temperature and urban heat indicators."),
            ("sar", "Synthetic Aperture Radar", "Backscatter, water detection, and flood extent."),
            ("land_cover", "Land-Cover Classification", "Urban, vegetation, bare ground, wetland, and water classes."),
            ("change_detection", "Change Detection", "Development, land cover, shoreline, and post-disaster change."),
            ("image_quality", "Image Quality", "Cloud masks, scene coverage, and sensor metadata."),
        ],
    ),
    _family(
        "geospatial_survey",
        "Geospatial Survey and Terrain",
        "Planned LiDAR, terrain, building, bathymetry, and datum workflows. The existing OSM2World viewer is separate from this agent.",
        [
            ("lidar", "LiDAR Point Cloud", "USGS 3DEP and related point clouds."),
            ("dtm", "Digital Terrain Model", "Bare-earth elevation rasters."),
            ("dsm", "Digital Surface Model", "First-return surface rasters."),
            ("building_footprint", "Building Footprint", "Footprint polygons tied to existing building identifiers."),
            ("building_height", "Building Height", "Height attributes with a stated source."),
            ("slope", "Terrain Slope", "Slope derived from a stated elevation model."),
            ("roughness", "Surface Roughness", "Roughness length or classification."),
            ("soil_geology", "Soil and Geology", "Soil and geologic units."),
            ("bathymetry", "Bathymetry", "Coastal bathymetric surfaces."),
            ("subsidence", "Land Subsidence", "Vertical land motion."),
            ("crs", "Coordinate Reference Systems", "CRS and axis-order checks."),
            ("datum_validation", "Geodetic Datum Validation", "Horizontal and vertical datum checks."),
            ("infrastructure_geometry", "Infrastructure Geometry", "Surveyed infrastructure geometry."),
        ],
    ),
    _family(
        "population",
        "Population and Demographics",
        "Planned aggregate census statistics. Individual household occupancy will not be inferred.",
        [
            ("population_density", "Population Density", "Aggregate population density."),
            ("census_geography", "Census Geography", "TIGER/Line and census unit boundaries."),
            ("age", "Age Distribution", "Aggregate age classes with margins of error."),
            ("households", "Household Composition", "Aggregate household characteristics."),
            ("housing", "Housing Characteristics", "Aggregate housing stock."),
            ("employment", "Employment Distribution", "Aggregate employment."),
            ("daytime_population", "Daytime Population Estimates", "Modeled daytime population, labeled as estimates."),
            ("social_vulnerability", "Social Vulnerability", "CDC/ATSDR SVI or a documented successor."),
            ("mobility", "Aggregate Mobility Patterns", "Aggregate mobility, not individual tracks."),
            ("evacuation_demand", "Evacuation Demand", "Aggregate demand estimates."),
            ("exposure", "Population Exposure", "Overlay of aggregate population and a hazard."),
            ("demographic_change", "Demographic Change", "Change between published vintages."),
        ],
    ),
    _family(
        "coastal",
        "Coastal, Ocean and Hydrology",
        "Planned water-level, wave, drainage, and flood products. Static flood zones are not dynamic simulations.",
        [
            ("tidal_water_levels", "Tidal Water Levels", "NOAA CO-OPS water levels."),
            ("sea_level", "Sea-Level Trends", "Published sea-level trend products."),
            ("storm_surge", "Storm Surge", "Surge model output with a named model."),
            ("wave_height", "Wave Height", "Observed or modeled wave height."),
            ("wave_period", "Wave Period", "Wave period."),
            ("wave_direction", "Wave Direction", "Wave direction."),
            ("currents", "Coastal Currents", "Current observations or model output."),
            ("bathymetry", "Coastal Bathymetry", "Bathymetry used by coastal models."),
            ("runoff", "Rainfall Runoff", "Runoff from a named hydrologic method."),
            ("surface_flow", "Surface Water Flow", "Streamflow and related observations."),
            ("drainage", "Drainage Infrastructure", "Authorized drainage assets."),
            ("flood_depth", "Flood Depth", "Depth from a named simulation or survey."),
            ("flood_extent", "Flood Extent", "Extent from a named simulation or survey."),
            ("flood_duration", "Flood Duration", "Duration from a time-varying water surface."),
            ("erosion", "Coastal Erosion", "Shoreline change from a named source."),
        ],
    ),
    _family(
        "transportation",
        "Transportation and Mobility",
        "Planned network and traffic products. Synthetic demand must stay labeled as synthetic.",
        [
            ("road_network", "Road Network", "OSM or an authoritative centerline network."),
            ("road_classification", "Road Classification", "Functional class."),
            ("capacity", "Road Capacity", "Capacity values with a stated source."),
            ("speed_limits", "Speed Limits", "Posted or mapped speed limits."),
            ("traffic_volume", "Traffic Volume", "Counts or clearly labeled synthetic demand."),
            ("congestion", "Congestion", "Observed or modeled congestion."),
            ("intersection_control", "Intersection Control", "Signals and stop control."),
            ("pedestrian", "Pedestrian Networks", "Walk network."),
            ("transit", "Public Transportation", "Routes and stops."),
            ("closures", "Road Closures", "Closure records."),
            ("emergency_routes", "Emergency Routes", "Designated routes."),
            ("freight", "Freight Movement", "Freight networks or statistics."),
            ("evacuation_routing", "Evacuation Routing", "Routing outputs from a named model."),
        ],
    ),
    _family(
        "urban_infrastructure",
        "Urban Infrastructure and Buildings",
        "Planned building and infrastructure attributes linked to existing Galveston building identifiers.",
        [
            ("building_geometry", "Building Geometry", "Geometry already reconstructed in the viewer, plus attributes."),
            ("building_classification", "Building Classification", "Use or occupancy class from a stated source."),
            ("building_height", "Building Height", "Height mapped to a building identifier."),
            ("building_footprint", "Building Footprint", "Footprints mapped to a building identifier."),
            ("building_exposure", "Building Exposure", "Exposure of buildings to a named hazard."),
            ("critical_facilities", "Critical Facilities", "Published facility locations."),
            ("bridges", "Bridges", "Bridge assets."),
            ("road_infrastructure", "Road Infrastructure", "Road structures."),
            ("public_buildings", "Public Buildings", "Public building inventory."),
            ("drainage_assets", "Drainage Assets", "Authorized drainage assets."),
            ("damage_states", "Structural Damage States", "Damage from a named method."),
            ("recovery", "Infrastructure Recovery", "Recovery timelines from a named method."),
        ],
    ),
    _family(
        "energy",
        "Energy and Utilities",
        "Planned utility research products. Actual grid topology will not be fabricated.",
        [
            ("electricity_demand", "Electricity Demand", "Authorized demand statistics."),
            ("distribution", "Distribution Network", "Authorized or explicitly synthetic networks."),
            ("substations", "Substation Assets", "Authorized substation locations."),
            ("renewable", "Renewable Generation", "Generation statistics or sites."),
            ("solar_potential", "Solar Potential", "Potential from a named irradiance and geometry method."),
            ("storage", "Energy Storage", "Storage assets."),
            ("outages", "Utility Outages", "Outage records."),
            ("restoration", "Restoration Scheduling", "Restoration plans or models."),
            ("water_distribution", "Water Distribution", "Authorized water-network data."),
            ("wastewater", "Wastewater Infrastructure", "Authorized wastewater data."),
            ("dependencies", "Infrastructure Dependencies", "Documented dependencies."),
        ],
    ),
    _family(
        "wireless",
        "Wireless Communications and IoT",
        "Planned radio and sensor research. Licensed sites and synthetic deployments stay distinct.",
        [
            ("base_stations", "Base Station Locations", "Authorized or synthetic site lists."),
            ("antennas", "Antenna Characteristics", "Antenna parameters for a stated configuration."),
            ("propagation", "Radio Propagation", "Output of a named propagation model."),
            ("path_loss", "Path Loss", "Path-loss results."),
            ("coverage", "Signal Coverage", "Coverage from a named model."),
            ("interference", "Interference", "Interference estimates."),
            ("capacity", "Network Capacity", "Capacity from a named model."),
            ("sensors", "Sensor Locations", "Research sensor locations."),
            ("iot_telemetry", "IoT Telemetry", "Telemetry from an authorized feed."),
            ("edge_nodes", "Edge Computing Nodes", "Node inventory."),
            ("network_failures", "Network Failures", "Failure scenarios."),
            ("uav_links", "UAV Communication Links", "Link budgets for a stated radio."),
        ],
    ),
    _family(
        "environmental",
        "Environmental and Ecological Intelligence",
        "Planned air, water, soil, wetland, and vegetation products from scientific sources.",
        [
            ("air_quality", "Air Quality", "Station or model air-quality data with a data kind."),
            ("particulate", "Particulate Matter", "PM observations or estimates."),
            ("ozone", "Ozone", "Ozone observations or estimates."),
            ("water_quality", "Water Quality", "Water-quality observations."),
            ("soil_moisture", "Soil Moisture", "In situ or satellite soil moisture, labeled accordingly."),
            ("wetlands", "Wetland Classification", "Wetland inventories."),
            ("vegetation_health", "Vegetation Health", "Indices from a named satellite product."),
            ("tree_canopy", "Tree Canopy", "Canopy datasets."),
            ("urban_heat", "Urban Heat Islands", "Heat indicators from a named method."),
            ("erosion", "Coastal Erosion", "Erosion from a named source."),
            ("exposure", "Environmental Exposure", "Aggregate exposure overlays."),
        ],
    ),
    _family(
        "seasonal",
        "Seasonal and Climate Intelligence",
        "Planned climatology and scenario comparisons. Normals are not forecasts.",
        [
            ("seasonal_rainfall", "Seasonal Rainfall", "Seasonal totals from a named baseline."),
            ("seasonal_temperature", "Seasonal Temperature", "Seasonal temperature statistics."),
            ("hurricane_season", "Hurricane Season Patterns", "Historical tropical-cyclone statistics."),
            ("climate_normals", "Monthly Climate Normals", "Published normals and their baseline period."),
            ("seasonal_wind", "Seasonal Wind", "Seasonal wind statistics."),
            ("daylight", "Daylight and Solar Cycles", "Astronomical daylight."),
            ("vegetation_seasonality", "Vegetation Seasonality", "Seasonal vegetation indices."),
            ("tourism_seasonality", "Tourism Seasonality", "Published tourism statistics."),
            ("climate_anomalies", "Historical Climate Anomalies", "Departures from a stated baseline."),
            ("climate_scenarios", "Climate Scenario Comparisons", "Named scenarios, not observations."),
        ],
    ),
    _family(
        "community_reports",
        "Community Forums and Public Reports",
        "Planned use of authorized public reports only. Reports stay unverified until corroborated, and identities are not collected.",
        [
            ("forums", "Public Forum Collection", "Authorized public sources only."),
            ("public_notices", "Official Public Notices", "Official notices."),
            ("incident_reports", "Community Incident Reports", "Unverified until corroborated."),
            ("complaints", "Infrastructure Complaints", "Authorized complaint summaries."),
            ("topics", "Topic Classification", "Classification with a stated method."),
            ("geo_mentions", "Geographic Mention Extraction", "Place mentions, not precise personal locations."),
            ("timelines", "Event Timeline Extraction", "Timelines extracted from public text."),
            ("sentiment", "Public Sentiment", "Aggregate sentiment."),
            ("concern_trends", "Community Concern Trends", "Aggregate trends."),
            ("credibility", "Source Credibility Assessment", "Source citations and confidence."),
        ],
    ),
    _family(
        "disaster",
        "Disaster Risk and Emergency Response",
        "Planned hazard and response research products. Outputs are non-operational and are not emergency guidance.",
        [
            ("hurricane_hazards", "Hurricane Hazards", "Hazards from named Weather and Coastal inputs."),
            ("flood_hazards", "Flood Hazards", "Hazards from named water and terrain inputs."),
            ("wind_damage", "Wind Damage", "Damage from a named vulnerability method."),
            ("infrastructure_exposure", "Critical Infrastructure Exposure", "Exposure overlays."),
            ("evacuation_zones", "Evacuation Zones", "Published zones."),
            ("shelters", "Shelter Accessibility", "Published shelters and access."),
            ("emergency_facilities", "Emergency Facility Locations", "Published facilities."),
            ("resources", "Resource Allocation", "Allocation from a named method."),
            ("damage_estimation", "Disaster Damage Estimation", "Estimates labeled as model output."),
            ("recovery_timelines", "Recovery Timelines", "Timelines from a named method."),
        ],
    ),
    _family(
        "autonomous_vehicles",
        "Autonomous UAV and UGV Operations",
        "Planned mission and mobility research. Viewer animation is not a vehicle-dynamics model.",
        [
            ("uav_missions", "UAV Mission Planning", "Mission plans."),
            ("ugv_missions", "UGV Mission Planning", "Ground mission plans."),
            ("vehicle_models", "Vehicle Models", "Named vehicle models."),
            ("obstacles", "Obstacle Detection", "Obstacles from a named sensor or map."),
            ("navigation_graphs", "Navigation Graphs", "Graphs derived from a stated map."),
            ("traversability", "Terrain Traversability", "Traversability from a stated terrain model."),
            ("sensors", "Sensor Models", "Named sensor models."),
            ("coordination", "Multi-Agent Coordination", "Coordination experiments."),
            ("comms_constraints", "Communication Constraints", "Constraints from a stated radio model."),
            ("energy", "Battery and Energy Modeling", "Energy from a stated model."),
            ("replay", "Mission Replay", "Replay of a stored mission."),
            ("collision_geometry", "Collision Geometry", "Geometry used for clearance checks."),
            ("disturbances", "Environmental Disturbances", "Wind or terrain disturbances from named inputs."),
        ],
    ),
    _family(
        "maritime",
        "Maritime and Port Operations",
        "Planned port and vessel products. AIS access must be checked for license before use.",
        [
            ("vessel_traffic", "Vessel Traffic", "Traffic from an authorized feed."),
            ("ais", "AIS Data", "AIS only after license and retention terms are recorded."),
            ("harbor", "Harbor Geography", "Harbor geography."),
            ("channels", "Shipping Channels", "Channel geometry."),
            ("berths", "Berth Infrastructure", "Berth inventory."),
            ("logistics", "Port Logistics", "Published logistics statistics."),
            ("maritime_weather", "Maritime Weather", "Marine weather from a named source."),
            ("restrictions", "Navigational Restrictions", "Published restrictions."),
            ("vessel_risk", "Coastal Vessel Risk", "Risk from a named method."),
            ("port_disruption", "Port Disruption Scenarios", "Scenarios labeled as simulations."),
        ],
    ),
    _family(
        "public_health",
        "Public Health and Exposure",
        "Planned aggregate health geography. Individual health profiles are out of scope.",
        [
            ("heat_exposure", "Heat Exposure", "Aggregate heat exposure."),
            ("flood_exposure", "Flood Exposure", "Aggregate flood exposure."),
            ("air_exposure", "Air Pollution Exposure", "Aggregate air exposure."),
            ("hospital_access", "Hospital Accessibility", "Access to published facilities."),
            ("ems", "Emergency Medical Resources", "Published resource locations."),
            ("vulnerability", "Aggregate Vulnerability", "Published vulnerability indices."),
            ("facilities", "Public Health Facility Distribution", "Published facilities."),
            ("environmental_health", "Environmental Health Risk", "Risk from named inputs."),
        ],
    ),
    _family(
        "economic",
        "Economic Activity and Land Use",
        "Planned aggregate economic statistics. Modeled estimates stay distinct from published statistics.",
        [
            ("land_use", "Land Use", "Land-use inventories."),
            ("zoning", "Zoning", "Municipal zoning."),
            ("commercial", "Commercial Activity", "Aggregate commercial statistics."),
            ("employment", "Employment", "Aggregate employment."),
            ("tourism", "Tourism", "Published tourism statistics."),
            ("property", "Property Characteristics", "Aggregate property characteristics."),
            ("development_change", "Development Change", "Change between published inventories."),
            ("economic_exposure", "Economic Exposure", "Exposure from a named method."),
            ("disruption_costs", "Infrastructure Disruption Costs", "Costs from a named method."),
            ("recovery", "Recovery Scenarios", "Scenarios labeled as models."),
        ],
    ),
    AgentDefinition(
        id="orchestration",
        name="Scenario and Experiment Orchestration",
        category="orchestration",
        description=(
            "Builds reproducible scenario manifests from datasets that are already in the catalog. "
            "It does not invent measurements, choose unstated model parameters, or launch a numerical model."
        ),
        implementation_status="limited",
        subagents=[
            SubagentDefinition(
                id="scenario_manifest",
                name="Scenario Manifest",
                parent_agent_id="orchestration",
                description="Saves a visualization scenario and the dataset versions attached to it.",
                implementation_status=ImplementationStatus.available,
                geographic_coverage="Regions declared on the attached datasets.",
                temporal_coverage="Time spans declared on the attached datasets.",
                output_schemas=["gdt.scenario.v1"],
                simulation_compatibility=[
                    "Visualization scenarios only.",
                    "Numerical simulation engines are not configured.",
                ],
            ),
            SubagentDefinition(
                id="experiment_gaps",
                name="Experiment Gaps",
                parent_agent_id="orchestration",
                description="Lists inputs that a rainfall-and-coastal flood experiment still lacks.",
                implementation_status=ImplementationStatus.limited,
                geographic_coverage="Galveston study area.",
                temporal_coverage="The interval the researcher selects.",
                simulation_compatibility=[
                    "Reports gaps. It does not run a flood model or fill the gaps with synthetic water.",
                ],
            ),
        ],
        simulation_outputs=["Scenario manifest", "Gap report"],
    ),
]


def _service(
    service_id: str,
    name: str,
    description: str,
    status: str,
) -> AgentDefinition:
    return AgentDefinition(
        id=service_id,
        name=name,
        category="infrastructure",
        description=description,
        implementation_status=status,
        subagents=[
            SubagentDefinition(
                id="service",
                name=name,
                parent_agent_id=service_id,
                description=description,
                implementation_status=(
                    ImplementationStatus.available if status == "operational" else ImplementationStatus.limited
                ),
                geographic_coverage="Applies to datasets in the catalog.",
                temporal_coverage="Applies to datasets in the catalog.",
            )
        ],
    )


SERVICES: list[AgentDefinition] = [
    _service(
        "data_discovery",
        "Data Discovery",
        "Searches the local catalog by agent, variable, time, source, and data kind. It does not crawl providers that are not connected.",
        "operational",
    ),
    _service(
        "data_quality",
        "Data Quality",
        "Records missing values, traces, range flags, units, and the limits of a station observation.",
        "operational",
    ),
    _service(
        "data_fusion",
        "Data Fusion",
        "Checks whether datasets may be combined. It refuses incompatible units, meanings, and undocumented station-to-grid broadcasts.",
        "operational",
    ),
    _service(
        "provenance",
        "Provenance",
        "Stores source, acquisition time, methodology, processing version, parent dataset, and license.",
        "operational",
    ),
    _service(
        "visualization",
        "Visualization",
        "Publishes station series as Cesium point markers with units, time, and source labels. It does not draw a city-wide surface from one station.",
        "operational",
    ),
    _service(
        "validation",
        "Validation",
        "Compares a processed series with an independent dataset when one is supplied. It does not claim validation without that reference.",
        "limited",
    ),
    _service(
        "experiment_reporting",
        "Experiment Reporting",
        "Exports the scenario manifest, dataset contracts, and quality notes that were actually stored.",
        "operational",
    ),
]


PROVIDERS: list[ProviderDefinition] = [
    ProviderDefinition(
        id="noaa_nws",
        name="NOAA National Weather Service API",
        documentation_url="https://www.weather.gov/documentation/services-web-api",
        implementation_status=ImplementationStatus.available,
        auth="none",
        data_kinds=["observation"],
        notes=(
            "api.weather.gov station observations. A descriptive User-Agent is required. "
            "Recent KGLS observations often leave precipitation unset. "
            "Feature geometry is rounded and is not used as the station location when station metadata is available."
        ),
        license="United States government work (public domain). Credit NOAA/NWS.",
    ),
    ProviderDefinition(
        id="iem_asos",
        name="Iowa Environmental Mesonet ASOS",
        documentation_url="https://mesonet.agron.iastate.edu/request/download.phtml",
        implementation_status=ImplementationStatus.available,
        auth="none",
        data_kinds=["observation"],
        notes=(
            "Historical NOAA ASOS/METAR reports redistributed by IEM. "
            "This connector requests routine reports only (report_type=3) so hourly accumulation is not double-counted. "
            "p01i is inches of precipitation in the hour ending at the report, not a 5-minute amount."
        ),
        license=(
            "NOAA ASOS observations are United States government work. "
            "Credit the Iowa Environmental Mesonet and NOAA/NWS when using the redistribution."
        ),
    ),
    ProviderDefinition(
        id="noaa_ncei_cdo",
        name="NOAA NCEI Climate Data Online",
        documentation_url="https://www.ncei.noaa.gov/cdo-web/webservices/v2",
        implementation_status=ImplementationStatus.unavailable,
        auth="token",
        credentials_env=["NCEI_CDO_TOKEN"],
        data_kinds=["observation"],
        notes="Documented for a later connector. No token is read and no sample climate rows are invented.",
        license="United States government work when used.",
    ),
    ProviderDefinition(
        id="noaa_coops",
        name="NOAA CO-OPS Tides and Currents",
        documentation_url="https://api.tidesandcurrents.noaa.gov/api/prod/",
        implementation_status=ImplementationStatus.unavailable,
        auth="none",
        data_kinds=["observation"],
        notes="Reserved for the Coastal Agent. Water levels are not estimated from rainfall.",
    ),
]


def all_agents() -> list[AgentDefinition]:
    return [*AGENTS, *SERVICES]


def get_agent(agent_id: str) -> AgentDefinition | None:
    for agent in all_agents():
        if agent.id == agent_id:
            return agent
    return None


def get_subagent(agent_id: str, subagent_id: str) -> SubagentDefinition | None:
    agent = get_agent(agent_id)
    if agent is None:
        return None
    for subagent in agent.subagents:
        if subagent.id == subagent_id:
            return subagent
    return None


def get_provider(provider_id: str) -> ProviderDefinition | None:
    for provider in PROVIDERS:
        if provider.id == provider_id:
            return provider
    return None
