import { create } from "zustand";
import type { ObservationRow } from "@/lib/agents/api";

export interface AgentSelection {
  key: string;
  agentId: string;
  agentLabel: string;
  subagentId: string;
  variableId: string;
  label: string;
  available: boolean;
}

export interface SceneSeries {
  datasetId: string;
  variable: string;
  unit: string;
  aggregation: string;
  title: string;
  observations: ObservationRow[];
}

export interface WeatherMapLayer {
  datasetId: string;
  title: string;
  variable: string;
  unit: string;
  aggregation: string;
  dataKind: string;
  sourceLabel: string;
  license: string | null;
  stationId: string;
  stationName: string;
  longitude: number;
  latitude: number;
  representativeness: string;
  displayNote: string;
  observations: ObservationRow[];
  series: SceneSeries[];
  clock: string[];
  index: number;
  playing: boolean;
  stepsPerSecond: number;
}

interface ResearchAgentState {
  selections: AgentSelection[];
  configureOpen: boolean;
  mapLayer: WeatherMapLayer | null;
  toggleSelection: (selection: AgentSelection) => void;
  setConfigureOpen: (open: boolean) => void;
  setMapLayer: (layer: WeatherMapLayer | null) => void;
  clearResearchScene: () => void;
  setMapIndex: (index: number) => void;
  setPlaying: (playing: boolean) => void;
  setStepsPerSecond: (stepsPerSecond: number) => void;
}

export const useResearchAgentStore = create<ResearchAgentState>((set) => ({
  selections: [],
  configureOpen: false,
  mapLayer: null,
  toggleSelection: (selection) =>
    set((state) => {
      const exists = state.selections.some((item) => item.key === selection.key);
      return {
        selections: exists
          ? state.selections.filter((item) => item.key !== selection.key)
          : [...state.selections, selection],
      };
    }),
  setConfigureOpen: (open) => set({ configureOpen: open }),
  setMapLayer: (layer) => set({ mapLayer: layer }),
  clearResearchScene: () => set({ mapLayer: null, selections: [], configureOpen: false }),
  setMapIndex: (index) =>
    set((state) => {
      if (!state.mapLayer) return state;
      const length = state.mapLayer.clock.length || state.mapLayer.observations.length;
      const last = Math.max(length - 1, 0);
      const next = Math.min(Math.max(index, 0), last);
      return { mapLayer: { ...state.mapLayer, index: next } };
    }),
  setPlaying: (playing) =>
    set((state) => (state.mapLayer ? { mapLayer: { ...state.mapLayer, playing } } : state)),
  setStepsPerSecond: (stepsPerSecond) =>
    set((state) =>
      state.mapLayer ? { mapLayer: { ...state.mapLayer, stepsPerSecond } } : state,
    ),
}));
