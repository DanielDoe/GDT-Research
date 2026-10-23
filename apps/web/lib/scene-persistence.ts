const STORAGE_KEY = "gdt-scene-modifications-v1";

export type PersistedSavedView = {
  id: string;
  name: string;
  longitude: number;
  latitude: number;
  height_m: number;
  heading_deg: number;
  pitch_deg: number;
};

export type PersistedSceneState = {
  hiddenBuildingIds: string[];
  savedViews: PersistedSavedView[];
  sceneObjectPatches: Array<{
    id: string;
    height_m?: number;
    heading_deg?: number;
    visible?: boolean;
  }>;
};

export function loadPersistedScene(): PersistedSceneState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedSceneState;
  } catch {
    return null;
  }
}

export function savePersistedScene(state: PersistedSceneState) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export function captureSceneState(
  viewerState: {
    hiddenBuildingIds: string[];
    savedViews: PersistedSavedView[];
  },
  sceneObjects: Array<{
    id: string;
    height_m: number;
    heading_deg: number;
    visible: boolean;
  }>,
): PersistedSceneState {
  return {
    hiddenBuildingIds: [...viewerState.hiddenBuildingIds],
    savedViews: viewerState.savedViews,
    sceneObjectPatches: sceneObjects.map((o) => ({
      id: o.id,
      height_m: o.height_m,
      heading_deg: o.heading_deg,
      visible: o.visible,
    })),
  };
}

export function clearPersistedScene() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}
