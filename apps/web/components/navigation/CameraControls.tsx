"use client";

import { CameraPresetKey, cameraPresets } from "@/lib/study-area";
import { Button } from "@/components/ui/button";
import { useViewerStore } from "@/stores/viewer-store";

const primaryPresets: CameraPresetKey[] = [
  "galveston_aerial",
  "downtown_3d",
  "street_level",
  "harbor_perspective",
  "building_closeup",
];

export function CameraControls() {
  const { setCameraPreset, addSavedView, cameraHud } = useViewerStore();

  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 px-3 py-2">
      {primaryPresets.map((key) => (
        <Button
          key={key}
          variant="secondary"
          size="sm"
          type="button"
          onClick={() => setCameraPreset(key)}
        >
          {cameraPresets[key].label}
        </Button>
      ))}
      <Button
        variant="outline"
        size="sm"
        type="button"
        disabled={!cameraHud}
        onClick={() => {
          if (!cameraHud) return;
          addSavedView({
            id: crypto.randomUUID(),
            name: `Saved ${new Date().toLocaleTimeString()}`,
            longitude: cameraHud.longitude,
            latitude: cameraHud.latitude,
            height_m: cameraHud.height_m,
            heading_deg: cameraHud.heading_deg,
            pitch_deg: cameraHud.pitch_deg,
          });
        }}
      >
        Save viewpoint
      </Button>
    </div>
  );
}
