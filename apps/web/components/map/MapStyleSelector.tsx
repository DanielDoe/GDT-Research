"use client";

import { Layers, Map, Mountain, Satellite, ScanSearch } from "lucide-react";
import { cn } from "@/lib/utils";
import { useViewerStore, type MapMode } from "@/stores/viewer-store";

const modes: {
  id: MapMode;
  label: string;
  description: string;
  icon: typeof Satellite;
  previewClass: string;
}[] = [
  {
    id: "satellite",
    label: "Satellite",
    description: "Flat aerial photo only",
    icon: Satellite,
    previewClass:
      "bg-[radial-gradient(circle_at_30%_20%,#3d6b4f_0%,#1a3d2e_40%,#0f172a_100%)]",
  },
  {
    id: "street",
    label: "Street Map",
    description: "Street map with building masses",
    icon: Map,
    previewClass:
      "bg-[linear-gradient(135deg,#e2e8f0_0%,#94a3b8_35%,#64748b_100%)]",
  },
  {
    id: "hybrid",
    label: "Hybrid",
    description: "Aerial photo, roads, and buildings",
    icon: Layers,
    previewClass:
      "bg-[linear-gradient(180deg,#2d5a3d_0%,#1e293b_55%),repeating-linear-gradient(90deg,transparent,transparent_8px,rgba(255,255,255,0.15)_8px,rgba(255,255,255,0.15)_9px)]",
  },
  {
    id: "terrain_3d",
    label: "3D Terrain",
    description: "Relief and buildings, no photo",
    icon: Mountain,
    previewClass:
      "bg-[linear-gradient(160deg,#4ade80_0%,#166534_45%,#0c4a6e_100%)]",
  },
  {
    id: "research_3d",
    label: "Research 3D",
    description: "Inspectable research masses",
    icon: ScanSearch,
    previewClass:
      "bg-[linear-gradient(135deg,#6366f1_0%,#312e81_50%,#0f172a_100%)]",
  },
];

export function MapStyleSelector() {
  const {
    mapMode,
    setMapMode,
    mapStyleSelectorOpen,
    setMapStyleSelectorOpen,
    status,
  } = useViewerStore();

  const active = modes.find((m) => m.id === mapMode) ?? modes[0];
  const ActiveIcon = active.icon;

  return (
    <div className="pointer-events-none absolute bottom-4 left-4 z-20 flex flex-col items-start gap-2 sm:bottom-5 sm:left-5">
      {mapStyleSelectorOpen && (
        <div
          className="pointer-events-auto w-[min(100vw-2rem,320px)] rounded-xl border border-slate-700/90 bg-slate-950/92 p-3 shadow-2xl backdrop-blur-md"
          role="dialog"
          aria-label="Map style"
        >
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Map style
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {modes.map((mode) => {
              const Icon = mode.icon;
              const selected = mapMode === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => {
                    setMapMode(mode.id);
                    setMapStyleSelectorOpen(false);
                  }}
                  className={cn(
                    "group flex flex-col overflow-hidden rounded-lg border text-left transition",
                    selected
                      ? "border-sky-400 ring-1 ring-sky-400/60"
                      : "border-slate-700 hover:border-slate-500",
                  )}
                >
                  <div
                    className={cn(
                      "relative h-14 w-full border-b border-slate-800/80",
                      mode.previewClass,
                    )}
                  >
                    <Icon className="absolute bottom-1.5 right-1.5 h-4 w-4 text-white/90 drop-shadow" />
                  </div>
                  <span className="px-2 py-1.5">
                    <span className="block text-[11px] font-medium text-slate-100">{mode.label}</span>
                    <span className="mt-0.5 block text-[9px] leading-snug text-slate-400">
                      {mode.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
          {status.imageryLoading && (
            <p className="mt-2 text-[10px] text-sky-300">Loading map tiles…</p>
          )}
          {status.satelliteImageryKind === "legacy_esri_tiles" && (
            <p className="mt-2 text-[10px] leading-snug text-amber-200/90">
              Using legacy Esri tile endpoint. Set NEXT_PUBLIC_ARCGIS_ACCESS_TOKEN for
              authenticated ArcGIS MapServer imagery.
            </p>
          )}
          {status.errorMessage && (
            <p className="mt-2 text-[10px] text-red-300">{status.errorMessage}</p>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={() => setMapStyleSelectorOpen(!mapStyleSelectorOpen)}
        className="pointer-events-auto flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-xs font-medium text-slate-100 shadow-lg backdrop-blur hover:bg-slate-900"
        aria-expanded={mapStyleSelectorOpen}
        aria-label="Choose map style"
      >
        <ActiveIcon className="h-4 w-4 text-sky-400" />
        <span>{active.label}</span>
      </button>
    </div>
  );
}
