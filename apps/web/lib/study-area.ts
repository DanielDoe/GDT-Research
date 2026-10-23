import studyAreaJson from "@/lib/data/study_area.json";

export type CameraPresetKey = keyof typeof studyAreaJson.camera_presets;

export interface CameraPreset {
  label: string;
  longitude: number;
  latitude: number;
  height_m: number;
  heading_deg?: number;
  pitch_deg?: number;
}

export const studyArea = studyAreaJson;

export const cameraPresets = studyAreaJson.camera_presets as Record<
  CameraPresetKey,
  CameraPreset
>;

export const cityCenter = studyAreaJson.city_center;

export const localOrigin = studyAreaJson.local_origin_wgs84;

export const studyBbox = studyAreaJson.bbox_wgs84;
