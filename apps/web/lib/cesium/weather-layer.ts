import type { ObservationRow } from "@/lib/agents/api";
import { studyBbox } from "@/lib/study-area";
import type { SceneSeries, WeatherMapLayer } from "@/stores/research-agent-store";

export const WEATHER_ENTITY_ID = "gdt-obs-station";
const RAIN_COLUMN_ID = "gdt-obs-rain-column";
const RAIN_DISC_ID = "gdt-obs-rain-disc";
const WIND_ID = "gdt-obs-wind";
const STUDY_ID = "gdt-obs-study";

/** Display scale for the gauge column. This is not a water depth. */
export const RAIN_METERS_PER_MM = 400;
/** Fixed disc around the gauge. The radius does not grow with rainfall. */
export const RAIN_DISC_RADIUS_M = 220;
const WIND_METERS_PER_MS = 80;

type CesiumModule = typeof import("cesium");

let flownDatasetId: string | null = null;

export function valueRgb(variable: string, value: number | null): [number, number, number] {
  if (value == null || Number.isNaN(value)) return [148, 163, 184];
  const span = variable.includes("precip") ? 20 : variable.includes("direction") ? 360 : 15;
  const t = Math.max(0, Math.min(1, value / span));
  return [
    Math.round(186 - t * 150),
    Math.round(214 - t * 40),
    Math.round(232 - t * 10),
  ];
}

export function rainColumnLength(value: number | null, flag: string | null): number | null {
  if (value == null) return flag === "trace" ? 90 : null;
  if (value <= 0) return 40;
  return Math.min(1500, Math.max(80, value * RAIN_METERS_PER_MM));
}

/** Meteorological direction is where the wind comes from. The arrow points downwind. */
export function downwindOffset(
  longitude: number,
  latitude: number,
  fromDegrees: number,
  lengthM: number,
): { longitude: number; latitude: number } {
  const to = ((fromDegrees + 180) % 360) * (Math.PI / 180);
  const latRad = latitude * (Math.PI / 180);
  return {
    longitude: longitude + (lengthM * Math.sin(to)) / (111_320 * Math.cos(latRad)),
    latitude: latitude + (lengthM * Math.cos(to)) / 111_320,
  };
}

export function rowAt(series: SceneSeries | undefined, time: string | undefined): ObservationRow | undefined {
  if (!series || !time) return undefined;
  return series.observations.find((row) => row.observed_at === time);
}

export function clockTime(layer: WeatherMapLayer): string | undefined {
  const clock = layer.clock ?? [];
  if (!clock.length) return layer.observations[layer.index]?.observed_at;
  return clock[Math.min(layer.index, clock.length - 1)];
}

export function seriesByVariable(layer: WeatherMapLayer, token: string): SceneSeries | undefined {
  return (layer.series ?? []).find((series) => series.variable.includes(token));
}

function material(Cesium: CesiumModule, red: number, green: number, blue: number, alpha: number) {
  return new Cesium.ColorMaterialProperty(Cesium.Color.fromBytes(red, green, blue, Math.round(alpha * 255)));
}

function drop(viewer: import("cesium").Viewer, id: string) {
  const existing = viewer.entities.getById(id);
  if (existing) viewer.entities.remove(existing);
}

export function syncWeatherStation(
  Cesium: CesiumModule,
  viewer: import("cesium").Viewer,
  layer: WeatherMapLayer | null,
  visible: boolean,
) {
  if (!layer || !(layer.clock?.length || layer.observations.length)) {
    for (const id of [WEATHER_ENTITY_ID, RAIN_COLUMN_ID, RAIN_DISC_ID, WIND_ID, STUDY_ID]) drop(viewer, id);
    flownDatasetId = null;
    return;
  }

  const time = clockTime(layer);
  const rain = rowAt(seriesByVariable(layer, "precip"), time);
  const speed = rowAt(seriesByVariable(layer, "wind_speed"), time);
  const direction = rowAt(seriesByVariable(layer, "wind_direction"), time);
  const gust = rowAt(seriesByVariable(layer, "wind_gust"), time);
  const primary = rowAt({ ...layer, observations: layer.observations }, time) ?? layer.observations[layer.index];
  const shown = rain ?? speed ?? direction ?? primary;
  const [red, green, blue] = valueRgb(rain ? "precip" : layer.variable, shown?.value ?? null);
  const color = Cesium.Color.fromBytes(red, green, blue, 230);
  const position = Cesium.Cartesian3.fromDegrees(layer.longitude, layer.latitude, 40);
  const ground = Cesium.Cartesian3.fromDegrees(layer.longitude, layer.latitude, 0);
  const lines = [
    layer.stationId || layer.stationName,
    time ?? "",
    rain ? `Rain ${rain.value == null ? rain.quality_flag ?? "missing" : `${rain.value} ${rain.unit}`} hourly accumulation` : null,
    speed ? `Wind ${speed.value == null ? "missing" : `${speed.value} ${speed.unit}`}` : null,
    direction
      ? `Direction ${direction.value == null ? direction.quality_flag ?? "missing" : `${direction.value}° from`}`
      : null,
    gust ? `Gust ${gust.value == null ? gust.quality_flag ?? "missing" : `${gust.value} ${gust.unit}`}` : null,
    "Gauge report, not a flood depth",
  ].filter(Boolean);

  upsertPoint(Cesium, viewer, position, ground, color, lines.join("\n"), visible);
  upsertRain(Cesium, viewer, layer, rain, visible);
  upsertWind(Cesium, viewer, layer, speed, direction, visible);
  upsertStudy(Cesium, viewer, visible);

  const viewKey = `${layer.datasetId}:gauge-northeast`;
  if (flownDatasetId !== viewKey) {
    flownDatasetId = viewKey;
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(-94.905, 29.228, 6500),
      orientation: {
        heading: Cesium.Math.toRadians(42),
        pitch: Cesium.Math.toRadians(-32),
        roll: 0,
      },
      duration: 1.4,
    });
  }
}

function upsertPoint(
  Cesium: CesiumModule,
  viewer: import("cesium").Viewer,
  position: import("cesium").Cartesian3,
  ground: import("cesium").Cartesian3,
  color: import("cesium").Color,
  label: string,
  visible: boolean,
) {
  const existing = viewer.entities.getById(WEATHER_ENTITY_ID);
  if (!existing) {
    viewer.entities.add({
      id: WEATHER_ENTITY_ID,
      position,
      point: {
        pixelSize: 14,
        color,
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      polyline: {
        positions: [ground, position],
        width: 2,
        material: new Cesium.ColorMaterialProperty(Cesium.Color.WHITE.withAlpha(0.85)),
      },
      label: {
        text: label,
        font: "12px sans-serif",
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.BLACK,
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -18),
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
        showBackground: true,
        backgroundColor: Cesium.Color.fromBytes(2, 6, 23, 200),
      },
      show: visible,
    });
    return;
  }
  existing.show = visible;
  existing.position = new Cesium.ConstantPositionProperty(position);
  if (existing.point) existing.point.color = new Cesium.ConstantProperty(color);
  if (existing.label) existing.label.text = new Cesium.ConstantProperty(label);
  if (existing.polyline) existing.polyline.positions = new Cesium.ConstantProperty([ground, position]);
}

function upsertRain(
  Cesium: CesiumModule,
  viewer: import("cesium").Viewer,
  layer: WeatherMapLayer,
  rain: ObservationRow | undefined,
  visible: boolean,
) {
  const length = rain ? rainColumnLength(rain.value, rain.quality_flag) : null;
  if (!seriesByVariable(layer, "precip") || length == null) {
    drop(viewer, RAIN_COLUMN_ID);
    drop(viewer, RAIN_DISC_ID);
    return;
  }
  const [red, green, blue] = valueRgb("precip", rain?.value ?? null);
  const center = Cesium.Cartesian3.fromDegrees(layer.longitude, layer.latitude, length / 2);
  const column = viewer.entities.getById(RAIN_COLUMN_ID);
  if (!column) {
    viewer.entities.add({
      id: RAIN_COLUMN_ID,
      position: center,
      cylinder: {
        length,
        topRadius: 22,
        bottomRadius: 22,
        material: material(Cesium, red, green, blue, 0.72),
        outline: true,
        outlineColor: Cesium.Color.WHITE.withAlpha(0.8),
      },
      show: visible,
    });
  } else {
    column.show = visible;
    column.position = new Cesium.ConstantPositionProperty(center);
    if (column.cylinder) {
      column.cylinder.length = new Cesium.ConstantProperty(length);
      column.cylinder.material = material(Cesium, red, green, blue, 0.72);
    }
  }
  const disc = viewer.entities.getById(RAIN_DISC_ID);
  const alpha = rain?.value == null ? 0.25 : 0.28 + 0.55 * Math.min(1, rain.value / 5);
  if (!disc) {
    viewer.entities.add({
      id: RAIN_DISC_ID,
      position: Cesium.Cartesian3.fromDegrees(layer.longitude, layer.latitude, 2),
      ellipse: {
        semiMajorAxis: RAIN_DISC_RADIUS_M,
        semiMinorAxis: RAIN_DISC_RADIUS_M,
        material: material(Cesium, red, green, blue, alpha),
        height: 2,
      },
      show: visible,
    });
  } else {
    disc.show = visible;
    if (disc.ellipse) disc.ellipse.material = material(Cesium, red, green, blue, alpha);
  }
}

function upsertWind(
  Cesium: CesiumModule,
  viewer: import("cesium").Viewer,
  layer: WeatherMapLayer,
  speed: ObservationRow | undefined,
  direction: ObservationRow | undefined,
  visible: boolean,
) {
  const speedValue = speed?.value ?? null;
  const from = direction?.value ?? null;
  const calm = speedValue === 0 || from == null || direction?.quality_flag === "calm";
  if (!seriesByVariable(layer, "wind_speed") || speedValue == null || calm) {
    drop(viewer, WIND_ID);
    return;
  }
  const length = Math.min(2000, 200 + speedValue * WIND_METERS_PER_MS);
  const tip = downwindOffset(layer.longitude, layer.latitude, from, length);
  const positions = [
    Cesium.Cartesian3.fromDegrees(layer.longitude, layer.latitude, 35),
    Cesium.Cartesian3.fromDegrees(tip.longitude, tip.latitude, 35),
  ];
  const existing = viewer.entities.getById(WIND_ID);
  if (!existing) {
    viewer.entities.add({
      id: WIND_ID,
      polyline: {
        positions,
        width: 6,
        material: new Cesium.PolylineArrowMaterialProperty(Cesium.Color.fromBytes(226, 232, 240, 230)),
      },
      show: visible,
    });
    return;
  }
  existing.show = visible;
  if (existing.polyline) existing.polyline.positions = new Cesium.ConstantProperty(positions);
}

function upsertStudy(Cesium: CesiumModule, viewer: import("cesium").Viewer, visible: boolean) {
  if (viewer.entities.getById(STUDY_ID)) {
    const existing = viewer.entities.getById(STUDY_ID);
    if (existing) existing.show = visible;
    return;
  }
  const { west, south, east, north } = studyBbox;
  const ring = [
    [west, south],
    [east, south],
    [east, north],
    [west, north],
    [west, south],
  ].flatMap(([lon, lat]) => [lon, lat, 25]);
  viewer.entities.add({
    id: STUDY_ID,
    polyline: {
      positions: Cesium.Cartesian3.fromDegreesArrayHeights(ring),
      width: 2,
      material: new Cesium.ColorMaterialProperty(Cesium.Color.WHITE.withAlpha(0.9)),
    },
    position: Cesium.Cartesian3.fromDegrees((west + east) / 2, (south + north) / 2, 40),
    label: {
      text: "Downtown study area\nNo water surface is drawn here",
      font: "12px sans-serif",
      fillColor: Cesium.Color.WHITE,
      outlineColor: Cesium.Color.BLACK,
      outlineWidth: 3,
      style: Cesium.LabelStyle.FILL_AND_OUTLINE,
      showBackground: true,
      backgroundColor: Cesium.Color.fromBytes(2, 6, 23, 180),
      disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },
    show: visible,
  });
}
