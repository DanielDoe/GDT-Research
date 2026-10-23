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
import { useSceneObjectStore } from "@/stores/scene-object-store";
import { useViewerStore } from "@/stores/viewer-store";

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
  const terrainLoadingRef = useRef(false);
  const sceneObjectEntityIds = useRef<Map<string, import("cesium").Entity>>(new Map());
  const measureEntitiesRef = useRef<import("cesium").Entity[]>([]);
  const measurePointsRef = useRef<import("cesium").Cartesian3[]>([]);
  const framedModelRef = useRef(false);
  const initCompleteRef = useRef(false);
  const [viewerReady, setViewerReady] = useState(false);
  const loadGenerationRef = useRef(0);
  const fpsFramesRef = useRef(0);
  const fpsLastRef = useRef(performance.now());
  const skipPresetFlyRef = useRef(true);
  const initSessionRef = useRef(0);
  const didInitialCameraRef = useRef(false);

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
  } = useViewerStore();

  const sceneObjects = useSceneObjectStore((s) => s.objects);

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
    highlightRef.current = viewer.entities.add({
      id: `gdt-highlight-${building.id}`,
      polygon: {
        hierarchy: Cesium.Cartesian3.fromDegreesArray(ring),
        height: 0,
        extrudedHeight: building.height_m,
        material: Cesium.Color.fromBytes(0, 220, 255, 90),
        outline: true,
        outlineColor: Cesium.Color.fromBytes(0, 255, 255, 220),
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
        if (catalog && useViewerStore.getState().buildingSourceMode === "gdt_reconstructed") {
          const nearest = findNearestBuilding(catalog, lon, lat);
          if (nearest) {
            showBuildingHighlight(Cesium, viewer, nearest);
            setSelectedObject({
              kind: "building",
              id: nearest.id,
              label: nearest.name,
              latitude: nearest.latitude,
              longitude: nearest.longitude,
              height_m: nearest.height_m,
              footprint_area_m2: nearest.footprint_area_m2,
              classification: nearest.building,
              data_source: nearest.source,
              quality: nearest.height_source,
              extra: { osm_id: nearest.osm_id },
            });
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
        syncCatalogOverlays(Cesium, viewer, catalog, {
          showFootprints: useViewerStore.getState().layers.buildingFootprints,
          showIdentifiers: useViewerStore.getState().layers.buildingIdentifiers,
        }, catalogOverlayEntities.current);
      });

      if (abortInit()) return;

      setStatus({ loadingMessage: null });
      applyCameraPreset(viewer, Cesium, "downtown_3d");

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

    const showGdt = buildingSourceMode === "gdt_reconstructed" && layers.reconstructedBuildings;
    if (reconstructedRef.current) {
      reconstructedRef.current.show = showGdt;
    } else if (showGdt) {
      void loadReconstructedModel(Cesium, true).then(() => {
        if (reconstructedRef.current) {
          void frameReconstructedModel(Cesium);
        }
      });
    }

    if (!showGdt) {
      clearBuildingHighlight(viewer);
    }

    viewer.scene.globe.show = layers.terrain || layers.imagery;

    const effectiveMaterial =
      mapMode === "research_3d" ? "research" : buildingMaterialMode;
    if (reconstructedRef.current?.model) {
      applyBuildingMaterialMode(Cesium, reconstructedRef.current.model, effectiveMaterial);
      const meshOpacity = proceduralGroundVisible ? reconstructionMeshOpacity : 0.35;
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
    layers.terrain,
    layers.imagery,
    proceduralGroundVisible,
    reconstructionMeshOpacity,
    viewerReady,
  ]);

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

    const wantsTerrain = mapMode === "terrain_3d" || layers.terrain;
    const ionPresent = (process.env.NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN ?? "").trim().length > 0;

    async function syncTerrain() {
      if (!Cesium || terrainLoadingRef.current) return;
      if (!wantsTerrain || !ionPresent) {
        if (!wantsTerrain && viewer) {
          viewer.terrainProvider = new Cesium.EllipsoidTerrainProvider();
          setStatus({ terrainSource: "ellipsoid" });
        }
        return;
      }
      terrainLoadingRef.current = true;
      try {
        viewer!.terrainProvider = await Cesium.createWorldTerrainAsync();
        setStatus({ terrainSource: "cesium_world" });
      } catch (err) {
        console.warn("Cesium World Terrain unavailable:", err);
      } finally {
        terrainLoadingRef.current = false;
      }
    }

    void syncTerrain();
  }, [mapMode, layers.terrain, viewerReady, setStatus]);

  useEffect(() => {
    const viewer = getLiveViewer();
    if (!viewer || !viewerReady) return;
    const exaggeration =
      terrainExaggerationEnabled && (mapMode === "terrain_3d" || layers.terrain)
        ? terrainExaggeration
        : 1;
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
    syncCatalogOverlays(
      Cesium,
      viewer,
      catalogRef.current,
      {
        showFootprints: layers.buildingFootprints,
        showIdentifiers: layers.buildingIdentifiers,
      },
      catalogOverlayEntities.current,
    );
  }, [layers.buildingFootprints, layers.buildingIdentifiers, viewerReady]);

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
