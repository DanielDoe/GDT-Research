import { create } from "zustand";

export type WorkspaceMode = "map" | "agents";

interface WorkspaceState {
  mode: WorkspaceMode;
  setMode: (mode: WorkspaceMode) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  mode: "map",
  setMode: (mode) => set({ mode }),
}));
