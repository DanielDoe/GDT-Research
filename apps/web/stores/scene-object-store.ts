import { create } from "zustand";
import type { SceneObjectRecord } from "@/lib/scene-objects/types";

interface SceneObjectState {
  objects: SceneObjectRecord[];
  selectedObjectId: string | null;
  selectObject: (id: string | null) => void;
  updateObject: (id: string, patch: Partial<SceneObjectRecord>) => void;
  resetDemoObjects: () => void;
}

const demoObjects: SceneObjectRecord[] = [
  {
    id: "gdt-demo-uav-1",
    kind: "simulation_entity",
    label: "Demo research UAV (not real infrastructure)",
    objectType: "quadrotor_uav",
    longitude: -94.79585,
    latitude: 29.30135,
    height_m: 45,
    heading_deg: 120,
    pitch_deg: 0,
    roll_deg: 0,
    dimensions_m: { length: 0.6, width: 0.6, height: 0.25 },
    visible: true,
    selected: false,
    simulationMeta: { role: "pathfinding_demo", max_speed_m_s: 12 },
  },
  {
    id: "gdt-demo-sensor-1",
    kind: "sensor",
    label: "Demo environmental sensor (not real infrastructure)",
    objectType: "fixed_sensor",
    longitude: -94.7952,
    latitude: 29.3010,
    height_m: 8,
    heading_deg: 0,
    pitch_deg: 0,
    roll_deg: 0,
    dimensions_m: { length: 0.4, width: 0.4, height: 1.2 },
    visible: true,
    selected: false,
    simulationMeta: { stream: "placeholder", units: "degC" },
  },
];

export const useSceneObjectStore = create<SceneObjectState>((set) => ({
  objects: demoObjects,
  selectedObjectId: null,
  selectObject: (id) =>
    set((state) => ({
      selectedObjectId: id,
      objects: state.objects.map((o) => ({ ...o, selected: o.id === id })),
    })),
  updateObject: (id, patch) =>
    set((state) => ({
      objects: state.objects.map((o) => (o.id === id ? { ...o, ...patch } : o)),
    })),
  resetDemoObjects: () => set({ objects: demoObjects, selectedObjectId: null }),
}));
