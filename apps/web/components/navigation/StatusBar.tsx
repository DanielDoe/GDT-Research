"use client";

import { useViewerStore } from "@/stores/viewer-store";

export function StatusBar() {
  const { cameraHud, selectedObject, activeScene, status } = useViewerStore();

  return (
    <footer className="flex h-10 items-center justify-between border-t border-slate-800 bg-slate-950/95 px-4 text-[11px] text-slate-400">
      <span>{activeScene}</span>
      <span>
        {cameraHud
          ? `Cam ${cameraHud.latitude.toFixed(5)}, ${cameraHud.longitude.toFixed(5)} · ${cameraHud.height_m.toFixed(0)} m`
          : "Camera —"}
      </span>
      <span>{selectedObject ? `Selected: ${selectedObject.id}` : "No selection"}</span>
      <span>
        {status.fpsEstimate != null ? `${status.fpsEstimate} fps · ` : ""}
        {status.loadingMessage ?? status.errorMessage ?? "Ready"}
      </span>
    </footer>
  );
}
