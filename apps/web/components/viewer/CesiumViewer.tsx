"use client";

import "cesium/Build/Cesium/Widgets/widgets.css";
import { useEffect, useRef, useState } from "react";
import { presetToFlyOptions } from "@/lib/cesium-camera";
import {
  applyMapMode,
  createImageryStack,
  imagerySourceLabel,
  type ImageryStackHandles,
} from "@/lib/cesium/imagery-providers";
import {
  applyBuildingMaterialMode,
  applyReconstructionMeshOpacity,
} from "@/lib/cesium/building-materials";
import { syncCatalogOverlays } from "@/lib/cesium/catalog-overlays";
import { syncCatalogBuildingVolumes } from "@/lib/cesium/catalog-building-layer";
import { createDemoDistrictTerrainProvider } from "@/lib/cesium/local-heightmap-terrain";
import { FirstPersonWalkController } from "@/lib/cesium/first-person-controller";
import {
  reconstructionOpacityForVisualization,
  resolveBuildingMaterial,
  shouldShowGeneratedBuildings,
} from "@/lib/scene-visualization";
import { loadPersistedScene } from "@/lib/scene-persistence";
import {
  configureCameraNavigation,
  configureSceneVisuals,
} from "@/lib/cesium/configure-navigation";
import { applyCameraPreset } from "@/lib/cesium/fly-to-study-area";
import {
  findNearestBuilding,
  loadBuildingCatalog,
  type BuildingCatalog,
} from "@/lib/building-catalog";
import {
  CameraPresetKey,
  cameraPresets,
  localOrigin,
  studyBbox,
} from "@/lib/study-area";
import { syncWeatherStation, WEATHER_ENTITY_ID } from "@/lib/cesium/weather-layer";
import { useResearchAgentStore } from "@/stores/research-agent-store";
import { useSceneObjectStore } from "@/stores/scene-object-store";
import { useViewerStore } from "@/stores/viewer-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

const RECONSTRUCTED_GLB = "/assets/galveston/galveston-demo.glb";
const TRANSFORM_JSON = "/assets/galveston/galveston-demo.transform.json";

type CesiumModule = typeof import("cesium");

const HUD_THROTTLE_MS = 100;

export function CesiumViewer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<import("cesium").Viewer | null>(null);
  const cesiumRef = useRef<CesiumModule | null>(null);
  const osmBuildingsRef = useRef<import("cesium").Cesium3DTileset | null>(null);
  const reconstructedRef = useRef<import("cesium").Entity | null>(null);
  const highlightRef = useRef<import("cesium").Entity | null>(null);
  const imageryHandlesRef = useRef<ImageryStackHandles | null>(null);
  const catalogRef = useRef<BuildingCatalog | null>(null);
  const catalogOverlayEntities = useRef<Map<string, import("cesium").Entity>>(new Map());
  const catalogVolumeEntities = useRef<Map<string, import("cesium").Entity>>(new Map());
  const terrainLoadingRef = useRef(false);
  const sceneObjectEntityIds = useRef<Map<string, import("cesium").Entity>>(new Map());
  const measureEntitiesRef = useRef<import("cesium").Entity[]>([]);
  const measurePointsRef = useRef<import("cesium").Cartesian3[]>([]);
  const framedModelRef = useRef(false);
  const initCompleteRef = useRef(false);
  const [viewerReady, setViewerReady] = useState(false);
  const [catalogVersion, setCatalogVersion] = useState(0);
  const loadGenerationRef = useRef(0);
  const fpsFramesRef = useRef(0);
  const fpsLastRef = useRef(performance.now());
  const skipPresetFlyRef = useRef(true);
  const initSessionRef = useRef(0);
  const didInitialCameraRef = useRef(false);
  const walkControllerRef = useRef<FirstPersonWalkController | null>(null);

  function getLiveViewer() {
    const viewer = viewerRef.current;
    if (!viewer || viewer.isDestroyed()) return null;
    return viewer;
  }

  const {
    buildingSourceMode,
    mapMode,
    buildingMaterialMode,
    viewSceneMode,
    interactionTool,
    layers,
    proceduralGroundVisible,
    reconstructionMeshOpacity,
    terrainExaggerationEnabled,
    terrainExaggeration,
    setStatus,
    setCameraHud,
    setSelectedObject,
    cameraPreset,
    cameraPresetEpoch,
    selectedObject,
    sceneVisualization,
    navigationMode,
    hiddenBuildingIds,
    walkMoveSpeedMps,
    walkEyeHeightM,
    restoreSceneModifications,
  } = useViewerStore();

  const sceneObjects = useSceneObjectStore((s) => s.objects);
  const weatherLayer = useResearchAgentStore((state) => state.mapLayer);
  const workspaceMode = useWorkspaceStore((state) => state.mode);

  async function frameReconstructedModel(Cesium: CesiumModule) {
    const viewer = getLiveViewer();
    if (!viewer || framedModelRef.current) return;
    framedModelRef.current = true;
    applyCameraPreset(viewer, Cesium, "downtown_3d");
  }

  function clearBuildingHighlight(viewer: import("cesium").Viewer) {
    if (highlightRef.current) {
      viewer.entities.remove(highlightRef.current);
      highlightRef.current = null;
    }
  }

  function showBuildingHighlight(
    Cesium: CesiumModule,
    viewer: import("cesium").Viewer,
    building: BuildingCatalog["buildings"][number],
  ) {
    clearBuildingHighlight(viewer);
    const ring = building.footprint_wgs84.flat();
    const base = building.ground_elevation_m ?? 0;
    highlightRef.current = viewer.entities.add({
      id: `gdt-highlight-${building.id}`,
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray(ring),
        height: base,
        extrudedHeight: base + building.height_m,
        material: Cesium.Color.fromBytes(0, 220, 255, 90),
        outline: true,
        outlineColor: Cesium.Color.fromBytes(0, 255, 255, 220),
      },
    });
  }

  function selectCatalogBuilding(
    Cesium: CesiumModule,
    viewer: import("cesium").Viewer,
    building: BuildingCatalog["buildings"][number],
  ) {
    showBuildingHighlight(Cesium, viewer, building);
    setSelectedObject({
      kind: "building",
      id: building.id,
      label: building.name,
      latitude: building.latitude,
      longitude: building.longitude,
      height_m: building.height_m,
      elevation_m: building.ground_elevation_m ?? undefined,
      footprint_area_m2: building.footprint_area_m2,
      classification: building.building,
      data_source: building.source,
      quality: building.quality_class ?? building.height_source,
      extra: {
        osm_id: building.osm_id,
        lod: building.lod ?? "LOD1",
        reconstruction_method: building.reconstruction_method ?? null,
        facade_material: building.facade_material ?? null,
        roof_material: building.roof_material ?? null,
        in_demo_district: building.in_demo_district ?? false,
      },
    });
  }

  function syncSceneObjects(Cesium: CesiumModule, viewer: import("cesium").Viewer) {
    const map = sceneObjectEntityIds.current;
    const liveIds = new Set(sceneObjects.map((o) => o.id));

    for (const [id, entity] of map) {
      if (!liveIds.has(id)) {
        viewer.entities.remove(entity);
        map.delete(id);
      }
    }

    for (const obj of sceneObjects) {
      let entity = map.get(obj.id);
      const position = Cesium.Cartesian3.fromDegrees(
        obj.longitude,
        obj.latitude,
        obj.height_m,
      );
      const dimensions = obj.dimensions_m ?? { length: 1, width: 1, height: 1 };
      if (!entity) {
        entity = viewer.entities.add({
          id: obj.id,
          name: obj.label,
          position,
          box: {
            dimensions: new Cesium.Cartesian3(
              dimensions.length,
              dimensions.width,
              dimensions.height,
            ),
            material: new Cesium.ColorMaterialProperty(
              obj.kind === "simulation_entity"
                ? Cesium.Color.fromBytes(255, 180, 0, 210)
                : Cesium.Color.fromBytes(120, 90, 255, 210),
            ),
            outline: true,
            outlineColor: Cesium.Color.WHITE,
          },
          label: {
            text: obj.label,
            font: "11px sans-serif",
            fillColor: Cesium.Color.WHITE,
            outlineColor: Cesium.Color.BLACK,
            outlineWidth: 2,
            style: Cesium.LabelStyle.FILL_AND_OUTLINE,
            verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
            pixelOffset: new Cesium.Cartesian2(0, -18),
            show: obj.visible,
          },
        });
        map.set(obj.id, entity);
      } else {
        entity.position = new Cesium.ConstantPositionProperty(position);
        const visible = obj.visible && (layers.researchAssets || layers.customAssets);
        entity.show = visible;
        if (entity.label) {
          entity.label.show = new Cesium.ConstantProperty(visible);
        }
      }
      if (entity.box) {
        entity.box.dimensions = new Cesium.ConstantProperty(
          new Cesium.Cartesian3(dimensions.length, dimensions.width, dimensions.height),
        );
      }
    }
  }

  useEffect(() => {
    const session = ++initSessionRef.current;
    let destroyed = false;
    let removePostRender: (() => void) | undefined;
    let handler: import("cesium").ScreenSpaceEventHandler | undefined;
    let localViewer: import("cesium").Viewer | null = null;

    const stale = () => destroyed || session !== initSessionRef.current;
    const abortInit = () => {
      if (stale()) {
        setStatus({ loadingMessage: null });
        return true;
      }
      return false;
    };

    async function init() {
      const container = containerRef.current;
      if (!container) return;
      setStatus({ loadingMessage: "Initializing 3D viewer…", errorMessage: null });

      const Cesium = await import("cesium");
      if (abortInit()) return;
      cesiumRef.current = Cesium;

      container.replaceChildren();

      const ionToken = (process.env.NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN ?? "").trim();
      Cesium.Ion.defaultAccessToken = ionToken;
      const ionPresent = ionToken.length > 0;

      const viewer = new Cesium.Viewer(container, {
        animation: false,
        timeline: false,
        geocoder: false,
        homeButton: false,
        sceneModePicker: false,
        baseLayerPicker: false,
        navigationHelpButton: false,
        fullscreenButton: false,
        infoBox: false,
        selectionIndicator: true,
        baseLayer: false,
        scene3DOnly: true,
        terrainProvider: new Cesium.EllipsoidTerrainProvider(),
        requestRenderMode: false,
      });
      if (abortInit()) {
        viewer.destroy();
        return;
      }

      localViewer = viewer;
      viewerRef.current = viewer;
      configureSceneVisuals(viewer, { realisticLighting: true });
      configureCameraNavigation(viewer);

      try {
        const stack = await createImageryStack(Cesium, viewer);
        if (abortInit()) {
          viewer.destroy();
          return;
        }
        imageryHandlesRef.current = stack.handles;
        const initialMode = useViewerStore.getState().mapMode;
        applyMapMode(stack.handles, initialMode, {
          imageryVisible: true,
          placeNamesOverlay: useViewerStore.getState().layers.placeNames,
          roadsOverlay: useViewerStore.getState().layers.roads,
        });
        setStatus({
          terrainSource: "ellipsoid",
          imagerySource: imagerySourceLabel(initialMode, stack.satelliteKind),
          satelliteImageryKind: stack.satelliteKind,
          satelliteImageryDetail: stack.satelliteDetail,
          ionTokenPresent: ionPresent,
          arcGisTokenPresent: Boolean(
            (process.env.NEXT_PUBLIC_ARCGIS_ACCESS_TOKEN ?? "").trim(),
          ),
          errorMessage: null,
        });
      } catch (err) {
        console.error(err);
        setStatus({
          errorMessage:
            err instanceof Error ? err.message : "Satellite imagery unavailable",
          satelliteImageryKind: "unavailable",
          ionTokenPresent: ionPresent,
        });
      }

      if (
        ionPresent &&
        (layers.terrain || useViewerStore.getState().mapMode === "terrain_3d")
      ) {
        try {
          viewer.terrainProvider = await Cesium.createWorldTerrainAsync();
          if (abortInit()) return;
          setStatus({ terrainSource: "cesium_world" });
        } catch (err) {
          console.warn("Cesium World Terrain unavailable:", err);
        }
      }

      if (ionPresent) {
        try {
          const osmBuildings = await Cesium.createOsmBuildingsAsync();
          if (abortInit()) return;
          osmBuildingsRef.current = osmBuildings;
          viewer.scene.primitives.add(osmBuildings);
          osmBuildings.show =
            buildingSourceMode === "reference_osm" && layers.referenceBuildings;
        } catch (err) {
          console.warn("Cesium OSM Buildings unavailable:", err);
        }
      }

      const studyFill = new Cesium.ColorMaterialProperty(
        Cesium.Color.fromBytes(0, 255, 255, 35),
      );
      viewer.entities.add({
        id: "gdt-study-area",
        polygon: {
          hierarchy: Cesium.Cartesian3.fromDegreesArray([
            studyBbox.west,
            studyBbox.south,
            studyBbox.east,
            studyBbox.south,
            studyBbox.east,
            studyBbox.north,
            studyBbox.west,
            studyBbox.north,
          ]),
          material: studyFill,
          outline: true,
          outlineColor: Cesium.Color.fromBytes(0, 255, 255, 160),
          height: 0,
        },
      });

      let lastHud = 0;
      removePostRender = viewer.scene.postRender.addEventListener(() => {
        fpsFramesRef.current += 1;
        const now = performance.now();
        if (now - fpsLastRef.current >= 1000) {
          setStatus({ fpsEstimate: fpsFramesRef.current });
          fpsFramesRef.current = 0;
          fpsLastRef.current = now;
        }

        if (now - lastHud < HUD_THROTTLE_MS) return;
        lastHud = now;
        const carto = Cesium.Cartographic.fromCartesian(viewer.camera.position);
        setCameraHud({
          longitude: Cesium.Math.toDegrees(carto.longitude),
          latitude: Cesium.Math.toDegrees(carto.latitude),
          height_m: carto.height,
          heading_deg: Cesium.Math.toDegrees(viewer.camera.heading),
          pitch_deg: Cesium.Math.toDegrees(viewer.camera.pitch),
        });

      });

      handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
      handler.setInputAction((movement: { position: import("cesium").Cartesian2 }) => {
        const tool = useViewerStore.getState().interactionTool;
        const cartesian = viewer.camera.pickEllipsoid(
          movement.position,
          viewer.scene.globe.ellipsoid,
        );
        if (!cartesian) return;

        if (tool === "pick_coordinate") {
          const carto = Cesium.Cartographic.fromCartesian(cartesian);
          setStatus({
            pickedCoordinate: {
              latitude: Cesium.Math.toDegrees(carto.latitude),
              longitude: Cesium.Math.toDegrees(carto.longitude),
              height_m: carto.height,
            },
          });
          return;
        }

        if (tool === "measure") {
          measurePointsRef.current.push(cartesian);
          const pointEntity = viewer.entities.add({
            position: cartesian,
            point: {
              pixelSize: 8,
              color: Cesium.Color.CYAN,
              outlineColor: Cesium.Color.BLACK,
              outlineWidth: 1,
            },
          });
          measureEntitiesRef.current.push(pointEntity);
          if (measurePointsRef.current.length === 2) {
            const [a, b] = measurePointsRef.current;
            const geodesic = new Cesium.EllipsoidGeodesic(
              Cesium.Cartographic.fromCartesian(a),
              Cesium.Cartographic.fromCartesian(b),
            );
            const distance = geodesic.surfaceDistance;
            setStatus({ measuredDistance_m: distance });
            const mid = Cesium.Cartesian3.midpoint(a, b, new Cesium.Cartesian3());
            const line = viewer.entities.add({
              position: mid,
              polyline: {
                positions: [a, b],
                width: 3,
                material: Cesium.Color.CYAN,
              },
              label: {
                text: `${distance.toFixed(1)} m`,
                font: "12px monospace",
                fillColor: Cesium.Color.WHITE,
                showBackground: true,
                backgroundColor: Cesium.Color.BLACK.withAlpha(0.65),
              },
            });
            measureEntitiesRef.current.push(line);
            measurePointsRef.current = [];
          }
          return;
        }

        const picked = viewer.scene.pick(movement.position);
        const pickedId =
          picked &&
          ((picked as { id?: string | { id?: string } }).id ??
            (picked as { primitive?: { id?: string } }).primitive?.id);
        const idStr =
          typeof pickedId === "string" ? pickedId : (pickedId as { id?: string })?.id;

        if (idStr?.startsWith("gdt-obs")) {
          const layer = useResearchAgentStore.getState().mapLayer;
          const time = layer ? layer.clock[layer.index] : undefined;
          const current = layer?.observations.find((row) => row.observed_at === time) ?? layer?.observations[layer.index ?? 0];
          const readings = Object.fromEntries(
            (layer?.series ?? []).map((series) => {
              const row = series.observations.find((item) => item.observed_at === time);
              return [series.variable, row?.value == null ? row?.quality_flag ?? "missing" : `${row.value} ${series.unit}`];
            }),
          );
          setSelectedObject({
            kind: "observation",
            id: layer?.stationId || WEATHER_ENTITY_ID,
            label: layer?.title,
            latitude: layer?.latitude,
            longitude: layer?.longitude,
            data_source: layer?.sourceLabel,
            quality: current?.quality_flag ?? layer?.dataKind,
            extra: {
              data_kind: layer?.dataKind ?? null,
              observed_at: time ?? null,
              ...readings,
              note: "Gauge playback. The column, disc, and arrow are symbols for the station report, not flood depth or extent.",
            },
          });
          return;
        }

        if (idStr?.startsWith("gdt-catalog-bldg-")) {
          const catalog = catalogRef.current;
          const buildingId = idStr
            .replace("gdt-catalog-bldg-", "")
            .replace(/-roof$/, "");
          const building = catalog?.buildings.find((b) => b.id === buildingId);
          if (building && !useViewerStore.getState().hiddenBuildingIds.includes(building.id)) {
            selectCatalogBuilding(Cesium, viewer, building);
            return;
          }
        }

        if (idStr?.startsWith("gdt-demo-")) {
          useSceneObjectStore.getState().selectObject(idStr);
          const obj = useSceneObjectStore.getState().objects.find((o) => o.id === idStr);
          setSelectedObject({
            kind: "simulation",
            id: idStr,
            label: obj?.label,
            latitude: obj?.latitude,
            longitude: obj?.longitude,
            height_m: obj?.height_m,
            data_source: "GDT simulation object registry",
            quality: "Demonstration entity (not real infrastructure)",
          });
          return;
        }

        const carto = Cesium.Cartographic.fromCartesian(cartesian);
        const lon = Cesium.Math.toDegrees(carto.longitude);
        const lat = Cesium.Math.toDegrees(carto.latitude);
        const catalog = catalogRef.current;
        const sourceMode = useViewerStore.getState().buildingSourceMode;
        if (
          catalog &&
          (sourceMode === "gdt_reconstructed" || sourceMode === "gdt_catalog_lod2")
        ) {
          const nearest = findNearestBuilding(
            catalog,
            lon,
            lat,
            80,
            new Set(useViewerStore.getState().hiddenBuildingIds),
          );
          if (nearest) {
            selectCatalogBuilding(Cesium, viewer, nearest);
            return;
          }
        }

        setSelectedObject(null);
        clearBuildingHighlight(viewer);
        useSceneObjectStore.getState().selectObject(null);
      }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

      syncSceneObjects(Cesium, viewer);

      void loadBuildingCatalog().then((catalog) => {
        catalogRef.current = catalog;
        setCatalogVersion((version) => version + 1);
        syncCatalogOverlays(Cesium, viewer, catalog, {
          showFootprints: useViewerStore.getState().layers.buildingFootprints,
          showIdentifiers: useViewerStore.getState().layers.buildingIdentifiers,
        }, catalogOverlayEntities.current);
      });

      if (abortInit()) return;

      setStatus({ loadingMessage: null });
      applyCameraPreset(viewer, Cesium, "downtown_3d");

      const persisted = loadPersistedScene();
      if (persisted?.hiddenBuildingIds?.length) {
        restoreSceneModifications(persisted.hiddenBuildingIds);
      }

      initCompleteRef.current = true;
      didInitialCameraRef.current = true;
      setViewerReady(true);
    }

    init().catch((err) => {
      console.error(err);
      setStatus({
        loadingMessage: null,
        errorMessage: err instanceof Error ? err.message : "Failed to initialize viewer",
      });
    });

    return () => {
      destroyed = true;
      initSessionRef.current += 1;
      initCompleteRef.current = false;
      didInitialCameraRef.current = false;
      setViewerReady(false);
      loadGenerationRef.current += 1;
      removePostRender?.();
      handler?.destroy();
      if (localViewer && !localViewer.isDestroyed()) {
        localViewer.destroy();
      }
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
      }
      viewerRef.current = null;
      containerRef.current?.replaceChildren();
      reconstructedRef.current = null;
      highlightRef.current = null;
      imageryHandlesRef.current = null;
      sceneObjectEntityIds.current.clear();
      measureEntitiesRef.current = [];
      measurePointsRef.current = [];
      framedModelRef.current = false;
      skipPresetFlyRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadReconstructedModel(Cesium: CesiumModule, visible: boolean) {
    const generation = loadGenerationRef.current;
    let viewer = getLiveViewer();
    if (!viewer) return;

    if (reconstructedRef.current) {
      viewer.entities.remove(reconstructedRef.current);
      reconstructedRef.current = null;
      framedModelRef.current = false;
    }

    viewer = getLiveViewer();
    if (!viewer || generation !== loadGenerationRef.current) return;

    let headingDeg = 0;
    try {
      const tr = await fetch(TRANSFORM_JSON);
      if (tr.ok) {
        const t = (await tr.json()) as { recommended_heading_deg?: number };
        headingDeg = t.recommended_heading_deg ?? 0;
      }
    } catch {
      /* optional */
    }

    const origin = Cesium.Cartesian3.fromDegrees(
      localOrigin.longitude,
      localOrigin.latitude,
      0,
    );
    const hpr = new Cesium.HeadingPitchRoll(Cesium.Math.toRadians(headingDeg), 0, 0);
    const orientation = Cesium.Transforms.headingPitchRollQuaternion(origin, hpr);

    const entity = viewer.entities.add({
      id: "gdt-reconstructed-city",
      name: "GDT reconstructed Galveston (OSM2World)",
      position: origin,
      orientation,
      model: {
        uri: RECONSTRUCTED_GLB,
        scale: 1.0,
        minimumPixelSize: 48,
        maximumScale: 20000,
      },
      show: visible,
    });

    reconstructedRef.current = entity;
    const effectiveMaterial =
      useViewerStore.getState().mapMode === "research_3d"
        ? "research"
        : useViewerStore.getState().buildingMaterialMode;
    applyBuildingMaterialMode(Cesium, entity.model, effectiveMaterial);
    applyReconstructionMeshOpacity(
      Cesium,
      entity.model,
      useViewerStore.getState().proceduralGroundVisible
        ? useViewerStore.getState().reconstructionMeshOpacity
        : 0.35,
      effectiveMaterial,
    );
    setStatus({
      reconstructedAssetLoaded: true,
      reconstructedAssetUrl: RECONSTRUCTED_GLB,
    });

    if (visible) {
      await frameReconstructedModel(Cesium);
    }
  }

  useEffect(() => {
    if (!viewerReady) return;
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium) return;

    if (osmBuildingsRef.current) {
      osmBuildingsRef.current.show =
        buildingSourceMode === "reference_osm" && layers.referenceBuildings;
    }

    const showGdt =
      shouldShowGeneratedBuildings(sceneVisualization) &&
      buildingSourceMode === "gdt_reconstructed" &&
      layers.reconstructedBuildings;
    if (reconstructedRef.current) {
      reconstructedRef.current.show = showGdt;
    } else if (showGdt) {
      void loadReconstructedModel(Cesium, true).then(() => {
        if (reconstructedRef.current) {
          void frameReconstructedModel(Cesium);
        }
      });
    }

    const showCatalogVolumes =
      mapMode !== "satellite" &&
      shouldShowGeneratedBuildings(sceneVisualization) &&
      buildingSourceMode === "gdt_catalog_lod2" &&
      layers.catalogVolumes;
    syncCatalogBuildingVolumes(
      Cesium,
      viewer,
      catalogRef.current,
      {
        show: showCatalogVolumes,
        hiddenBuildingIds: new Set(hiddenBuildingIds),
        debugGeometry:
          mapMode === "research_3d" ||
          sceneVisualization === "research_geometry" ||
          buildingMaterialMode === "research",
        demoDistrictOnly: false,
        useEpqsGroundElevation: layers.localDemoTerrain,
      },
      catalogVolumeEntities.current,
    );

    if (!showGdt && !showCatalogVolumes) {
      clearBuildingHighlight(viewer);
    }

    viewer.scene.globe.show = layers.terrain || layers.imagery;

    const effectiveMaterial = resolveBuildingMaterial(
      sceneVisualization,
      mapMode === "research_3d" ? "research" : buildingMaterialMode,
    );
    if (reconstructedRef.current?.model) {
      applyBuildingMaterialMode(Cesium, reconstructedRef.current.model, effectiveMaterial);
      const meshOpacity = reconstructionOpacityForVisualization(
        sceneVisualization,
        proceduralGroundVisible,
        reconstructionMeshOpacity,
      );
      applyReconstructionMeshOpacity(
        Cesium,
        reconstructedRef.current.model,
        meshOpacity,
        effectiveMaterial,
      );
    }

    configureSceneVisuals(viewer, {
      realisticLighting: effectiveMaterial === "realistic",
    });
  }, [
    buildingSourceMode,
    buildingMaterialMode,
    mapMode,
    layers.referenceBuildings,
    layers.reconstructedBuildings,
    layers.catalogVolumes,
    layers.terrain,
    layers.imagery,
    proceduralGroundVisible,
    reconstructionMeshOpacity,
    sceneVisualization,
    hiddenBuildingIds,
    layers.localDemoTerrain,
    viewerReady,
    catalogVersion,
  ]);

  useEffect(() => {
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !viewerReady) return;

    const controller = viewer.scene.screenSpaceCameraController;
    if (navigationMode === "walk") {
      if (!walkControllerRef.current) {
        walkControllerRef.current = new FirstPersonWalkController(viewer, Cesium, {
          moveSpeedMps: walkMoveSpeedMps,
          eyeHeightM: walkEyeHeightM,
        });
      }
      walkControllerRef.current.setMoveSpeed(walkMoveSpeedMps);
      walkControllerRef.current.setEyeHeight(walkEyeHeightM);
      walkControllerRef.current.start();
      controller.enableLook = false;
      controller.enableRotate = false;
      controller.enableTranslate = false;
      controller.enableZoom = false;
      controller.enableTilt = false;
    } else {
      walkControllerRef.current?.stop();
      configureCameraNavigation(viewer);
      if (navigationMode === "fly") {
        controller.enableLook = true;
        controller.enableTranslate = true;
        controller.enableTilt = true;
        controller.enableCollisionDetection = false;
      }
    }

    return () => {
      walkControllerRef.current?.stop();
    };
  }, [navigationMode, viewerReady, walkMoveSpeedMps, walkEyeHeightM]);

  useEffect(() => {
    if (!viewerReady) return;
    const hidden = new Set(hiddenBuildingIds);
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium) return;
    syncCatalogOverlays(
      Cesium,
      viewer,
      catalogRef.current,
      {
        showFootprints: layers.buildingFootprints,
        showIdentifiers: layers.buildingIdentifiers,
        hiddenBuildingIds: hidden,
      },
      catalogOverlayEntities.current,
    );
    if (
      selectedObject?.kind === "building" &&
      selectedObject.id &&
      hidden.has(selectedObject.id)
    ) {
      clearBuildingHighlight(viewer);
    }
  }, [hiddenBuildingIds, layers.buildingFootprints, layers.buildingIdentifiers, selectedObject?.id, selectedObject?.kind, viewerReady]);

  useEffect(() => {
    if (!viewerReady) return;
    const handles = imageryHandlesRef.current;
    if (!handles) return;
    applyMapMode(handles, mapMode, {
      imageryVisible: layers.imagery,
      placeNamesOverlay: layers.placeNames,
      roadsOverlay: layers.roads,
    });
    const kind = useViewerStore.getState().status.satelliteImageryKind;
    setStatus({ imagerySource: imagerySourceLabel(mapMode, kind) });
  }, [mapMode, layers.imagery, layers.placeNames, layers.roads, viewerReady, setStatus]);

  useEffect(() => {
    if (!viewerReady) return;
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium) return;

    const useLocalDemo = layers.localDemoTerrain && mapMode !== "satellite";
    const ionPresent = (process.env.NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN ?? "").trim().length > 0;

    if (mapMode === "research_3d") {
      viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#221a45");
      viewer.scene.globe.showGroundAtmosphere = false;
    } else if (mapMode === "terrain_3d") {
      viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#6d7d58");
      viewer.scene.globe.showGroundAtmosphere = true;
    } else {
      viewer.scene.globe.baseColor = Cesium.Color.fromCssColorString("#1c2834");
      viewer.scene.globe.showGroundAtmosphere = true;
    }

    let cancelled = false;
    async function syncTerrain() {
      if (!Cesium || !viewer) return;
      const flatPhoto =
        mapMode === "satellite" || mapMode === "street" || mapMode === "hybrid" || mapMode === "research_3d";
      terrainLoadingRef.current = true;
      try {
        if (useLocalDemo && mapMode === "terrain_3d") {
          const local = await createDemoDistrictTerrainProvider(Cesium);
          if (cancelled || !local) return;
          viewer.terrainProvider = local;
          setStatus({ terrainSource: "demo_epqs_heightmap" });
          return;
        }
        if (flatPhoto) {
          viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
          setStatus({ terrainSource: "ellipsoid" });
          return;
        }
        try {
          const elevation = await Cesium.ArcGISTiledElevationTerrainProvider.fromUrl(
            "https://elevation3d.arcgis.com/arcgis/rest/services/WorldElevation3D/Terrain3D/ImageServer",
          );
          if (cancelled) return;
          viewer.terrainProvider = elevation;
          setStatus({ terrainSource: "arcgis_world_elevation" });
          return;
        } catch (err) {
          console.warn("ArcGIS World Elevation unavailable:", err);
        }
        if (ionPresent) {
          try {
            const world = await Cesium.createWorldTerrainAsync();
            if (cancelled) return;
            viewer.terrainProvider = world;
            setStatus({ terrainSource: "cesium_world" });
            return;
          } catch (err) {
            console.warn("Cesium World Terrain unavailable:", err);
          }
        }
        if (cancelled) return;
        viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
        setStatus({ terrainSource: "ellipsoid" });
      } finally {
        terrainLoadingRef.current = false;
      }
    }

    void syncTerrain();
    return () => {
      cancelled = true;
    };
  }, [mapMode, layers.terrain, layers.localDemoTerrain, viewerReady, setStatus]);

  useEffect(() => {
    const viewer = getLiveViewer();
    if (!viewer || !viewerReady) return;
    const exaggeration = mapMode === "terrain_3d" ? terrainExaggeration : 1;
    viewer.scene.verticalExaggeration = exaggeration;
    viewer.scene.verticalExaggerationRelativeHeight = 0;
  }, [
    terrainExaggerationEnabled,
    terrainExaggeration,
    mapMode,
    layers.terrain,
    viewerReady,
  ]);

  useEffect(() => {
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !viewerReady) return;
    viewer.scene.mode =
      viewSceneMode === "3d" ? Cesium.SceneMode.SCENE3D : Cesium.SceneMode.SCENE2D;
  }, [viewSceneMode]);

  useEffect(() => {
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !viewerReady) return;
    syncSceneObjects(Cesium, viewer);
  }, [sceneObjects, layers.customAssets, layers.researchAssets, viewerReady]);

  useEffect(() => {
    const viewer = getLiveViewer();
    if (!viewer || !viewerReady || workspaceMode !== "map") return;
    viewer.resize();
    viewer.scene.requestRender();
  }, [workspaceMode, viewerReady]);

  useEffect(() => {
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !viewerReady) return;
    try {
      syncWeatherStation(Cesium, viewer, weatherLayer, layers.researchAssets);
    } catch (error) {
      console.error("Weather station marker was not drawn.", error);
    }
  }, [weatherLayer, layers.researchAssets, viewerReady, workspaceMode]);

  useEffect(() => {
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium || !viewerReady) return;
    if (skipPresetFlyRef.current) {
      skipPresetFlyRef.current = false;
      return;
    }

    let preset = cameraPresets[cameraPreset as CameraPresetKey];
    if (
      cameraPreset === "building_closeup" &&
      selectedObject?.kind === "building" &&
      selectedObject.latitude != null &&
      selectedObject.longitude != null
    ) {
      preset = {
        ...preset,
        longitude: selectedObject.longitude,
        latitude: selectedObject.latitude,
        height_m: Math.max(55, (selectedObject.height_m ?? 12) * 5),
      };
    }

    viewer.camera.flyTo({
      ...presetToFlyOptions(preset, Cesium),
      duration: 1.35,
    });
    viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  }, [cameraPreset, cameraPresetEpoch, selectedObject?.id, viewerReady]);

  useEffect(() => {
    if (!viewerReady || didInitialCameraRef.current) return;
    const viewer = getLiveViewer();
    const Cesium = cesiumRef.current;
    if (!viewer || !Cesium) return;
    didInitialCameraRef.current = true;
    applyCameraPreset(viewer, Cesium, "downtown_3d");
  }, [viewerReady]);

  useEffect(() => {
    if (interactionTool !== "measure") {
      const viewer = getLiveViewer();
      if (!viewer) return;
      for (const e of measureEntitiesRef.current) {
        viewer.entities.remove(e);
      }
      measureEntitiesRef.current = [];
      measurePointsRef.current = [];
      setStatus({ measuredDistance_m: null });
    }
  }, [interactionTool, setStatus]);

  return (
    <div ref={containerRef} className="absolute inset-0 h-full w-full overflow-hidden" />
  );
}
