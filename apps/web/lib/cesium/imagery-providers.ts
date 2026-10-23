import type { MapMode } from "@/stores/viewer-store";

/** Legacy public tile endpoint (no token). Used only when ArcGIS API auth fails — never labeled as a different mode. */
export const ESRI_WORLD_IMAGERY_TILES =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

export const ESRI_WORLD_STREET_MAP =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer";

export const ESRI_REFERENCE_LABELS =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer";

export const ESRI_REFERENCE_ROADS =
  "https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer";

export const OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export type SatelliteImageryKind =
  | "arcgis_map_server"
  | "legacy_esri_tiles"
  | "cesium_ion"
  | "unavailable";

export type ImageryStackHandles = {
  satellite: import("cesium").ImageryLayer;
  street: import("cesium").ImageryLayer;
  labels: import("cesium").ImageryLayer;
  roadLabels: import("cesium").ImageryLayer;
};

export function configureArcGisCredentials(Cesium: typeof import("cesium")) {
  const token = (process.env.NEXT_PUBLIC_ARCGIS_ACCESS_TOKEN ?? "").trim();
  if (token) {
    Cesium.ArcGisMapService.defaultAccessToken = token;
  }
}

export function arcGisTokenPresent(): boolean {
  return Boolean((process.env.NEXT_PUBLIC_ARCGIS_ACCESS_TOKEN ?? "").trim());
}

async function createSatelliteProvider(Cesium: typeof import("cesium")): Promise<{
  provider: import("cesium").ImageryProvider;
  kind: SatelliteImageryKind;
  detail: string;
}> {
  configureArcGisCredentials(Cesium);

  try {
    const provider = await Cesium.ArcGisMapServerImageryProvider.fromBasemapType(
      Cesium.ArcGisBaseMapType.SATELLITE,
    );
    return {
      provider,
      kind: "arcgis_map_server",
      detail: "ArcGIS World Imagery (MapServer)",
    };
  } catch (err) {
    console.warn("ArcGIS World Imagery (authenticated) unavailable:", err);
  }

  try {
    const provider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
      "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
    );
    return {
      provider,
      kind: "arcgis_map_server",
      detail: "ArcGIS World Imagery (services.arcgisonline.com)",
    };
  } catch (err) {
    console.warn("ArcGIS World Imagery (fromUrl) unavailable:", err);
  }

  try {
    const provider = new Cesium.UrlTemplateImageryProvider({
      url: ESRI_WORLD_IMAGERY_TILES,
      credit: "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
      maximumLevel: 19,
    });
    return {
      provider,
      kind: "legacy_esri_tiles",
      detail: "Esri World Imagery (legacy tile endpoint)",
    };
  } catch (err) {
    console.warn("Legacy Esri tile endpoint unavailable:", err);
  }

  const ionToken = (process.env.NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN ?? "").trim();
  if (ionToken) {
    try {
      Cesium.Ion.defaultAccessToken = ionToken;
      const provider = await Cesium.createWorldImageryAsync({
        style: Cesium.IonWorldImageryStyle.AERIAL,
      });
      return {
        provider,
        kind: "cesium_ion",
        detail: "Cesium ion global imagery (Bing aerial)",
      };
    } catch (err) {
      console.warn("Cesium ion world imagery unavailable:", err);
    }
  }

  throw new Error(
    "Satellite imagery could not be loaded. Configure NEXT_PUBLIC_ARCGIS_ACCESS_TOKEN or NEXT_PUBLIC_CESIUM_ION_ACCESS_TOKEN.",
  );
}

async function createStreetProvider(Cesium: typeof import("cesium")) {
  configureArcGisCredentials(Cesium);
  try {
    return await Cesium.ArcGisMapServerImageryProvider.fromUrl(ESRI_WORLD_STREET_MAP);
  } catch {
    return new Cesium.UrlTemplateImageryProvider({
      url: OSM_TILE_URL,
      credit: "© OpenStreetMap contributors",
    });
  }
}

async function createReferenceProvider(Cesium: typeof import("cesium"), url: string) {
  configureArcGisCredentials(Cesium);
  return Cesium.ArcGisMapServerImageryProvider.fromUrl(url, {
    enablePickFeatures: false,
  });
}

/** Transparent 1×1 placeholder when a reference overlay cannot be loaded. */
function createEmptyOverlayProvider(Cesium: typeof import("cesium")) {
  return new Cesium.SingleTileImageryProvider({
    url: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+Zk2EAAAAASUVORK5CYII=",
    rectangle: Cesium.Rectangle.fromDegrees(-180, -90, 180, 90),
  });
}

export async function createImageryStack(
  Cesium: typeof import("cesium"),
  viewer: import("cesium").Viewer,
): Promise<{
  handles: ImageryStackHandles;
  satelliteKind: SatelliteImageryKind;
  satelliteDetail: string;
}> {
  const { provider, kind, detail } = await createSatelliteProvider(Cesium);
  const streetProvider = await createStreetProvider(Cesium);
  let labelsProvider: import("cesium").ImageryProvider;
  let roadLabelsProvider: import("cesium").ImageryProvider;
  try {
    labelsProvider = await createReferenceProvider(Cesium, ESRI_REFERENCE_LABELS);
  } catch (err) {
    console.warn("Place-name reference overlay unavailable:", err);
    labelsProvider = createEmptyOverlayProvider(Cesium);
  }
  try {
    roadLabelsProvider = await createReferenceProvider(Cesium, ESRI_REFERENCE_ROADS);
  } catch (err) {
    console.warn("Road reference overlay unavailable:", err);
    roadLabelsProvider = createEmptyOverlayProvider(Cesium);
  }

  const satellite = viewer.imageryLayers.addImageryProvider(provider);
  const street = viewer.imageryLayers.addImageryProvider(streetProvider);
  const labels = viewer.imageryLayers.addImageryProvider(labelsProvider);
  const roadLabels = viewer.imageryLayers.addImageryProvider(roadLabelsProvider);

  street.show = false;
  labels.show = false;
  roadLabels.show = false;
  labels.alpha = 0.92;
  roadLabels.alpha = 0.75;

  attachImageryErrorHandler(satellite, "Satellite imagery");
  attachImageryErrorHandler(street, "Street map");
  attachImageryErrorHandler(labels, "Map labels");
  attachImageryErrorHandler(roadLabels, "Road labels");

  return {
    handles: { satellite, street, labels, roadLabels },
    satelliteKind: kind,
    satelliteDetail: detail,
  };
}

function attachImageryErrorHandler(layer: import("cesium").ImageryLayer, label: string) {
  const provider = layer.imageryProvider;
  if (provider && "errorEvent" in provider) {
    (provider as import("cesium").ImageryProvider).errorEvent.addEventListener((err: unknown) => {
      console.warn(`${label} tile error:`, err);
    });
  }
}

export function applyMapMode(
  handles: ImageryStackHandles,
  mode: MapMode,
  options: {
    imageryVisible: boolean;
    placeNamesOverlay: boolean;
    roadsOverlay: boolean;
  },
) {
  const { satellite, street, labels, roadLabels } = handles;
  const showImagery = options.imageryVisible;

  const showSatellite =
    showImagery &&
    (mode === "satellite" ||
      mode === "hybrid" ||
      mode === "terrain_3d" ||
      mode === "research_3d");
  const showStreet = showImagery && mode === "street";
  const showHybridLabels =
    showImagery && (mode === "hybrid" || (options.placeNamesOverlay && mode !== "street"));
  const showRoadOverlay =
    showImagery && (mode === "hybrid" || (options.roadsOverlay && showSatellite));

  satellite.show = showSatellite;
  street.show = showStreet;
  labels.show = showHybridLabels;
  roadLabels.show = showRoadOverlay;

  if (showSatellite) {
    satellite.alpha = 1;
  }
  if (showStreet) {
    street.alpha = 0.95;
  }
}

export function imagerySourceLabel(
  mode: MapMode,
  satelliteKind: SatelliteImageryKind | null,
): string {
  if (mode === "street") return "street_cartographic";
  if (mode === "hybrid") return satelliteKind ? `hybrid_${satelliteKind}` : "hybrid";
  if (satelliteKind === "arcgis_map_server") return "arcgis_world_imagery";
  if (satelliteKind === "legacy_esri_tiles") return "esri_legacy_tiles";
  if (satelliteKind === "cesium_ion") return "cesium_ion_aerial";
  return "unavailable";
}
