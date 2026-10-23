export type SceneObjectKind = "simulation_entity" | "sensor" | "user_asset";

export interface SceneObjectRecord {
  id: string;
  kind: SceneObjectKind;
  label: string;
  objectType: string;
  longitude: number;
  latitude: number;
  height_m: number;
  heading_deg: number;
  pitch_deg: number;
  roll_deg: number;
  dimensions_m?: { length: number; width: number; height: number };
  visible: boolean;
  selected: boolean;
  simulationMeta?: Record<string, string | number | boolean>;
}
