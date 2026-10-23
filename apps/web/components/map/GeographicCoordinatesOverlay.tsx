"use client";

import { useViewerStore } from "@/stores/viewer-store";

export function GeographicCoordinatesOverlay() {
  const { layers, cameraHud, status } = useViewerStore();
  if (!layers.geographicCoordinates) return null;

  return (
    <>
      <div
        className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center"
        aria-hidden
      >
        <div className="h-8 w-8 rounded-full border border-cyan-400/70" />
        <div className="absolute h-px w-10 bg-cyan-400/80" />
        <div className="absolute h-10 w-px bg-cyan-400/80" />
      </div>
      <div className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 rounded-md bg-black/60 px-2 py-1 font-mono text-[10px] text-cyan-100">
        {cameraHud
          ? `${cameraHud.latitude.toFixed(6)}, ${cameraHud.longitude.toFixed(6)} · ${cameraHud.height_m.toFixed(1)} m`
          : "Coordinates —"}
        {status.pickedCoordinate && (
          <span className="ml-2 text-slate-300">
            Picked {status.pickedCoordinate.latitude.toFixed(6)},{" "}
            {status.pickedCoordinate.longitude.toFixed(6)}
          </span>
        )}
      </div>
    </>
  );
}
