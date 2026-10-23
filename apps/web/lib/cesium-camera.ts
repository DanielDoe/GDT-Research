import type { CameraPreset } from "@/lib/study-area";

export interface CameraPresetExtended extends CameraPreset {
  heading_deg?: number;
  pitch_deg?: number;
}

export function presetToFlyOptions(
  preset: CameraPresetExtended,
  Cesium: typeof import("cesium"),
) {
  return {
    destination: Cesium.Cartesian3.fromDegrees(
      preset.longitude,
      preset.latitude,
      preset.height_m,
    ),
    orientation: {
      heading: Cesium.Math.toRadians(preset.heading_deg ?? 0),
      pitch: Cesium.Math.toRadians(preset.pitch_deg ?? -35),
      roll: 0,
    },
  };
}
