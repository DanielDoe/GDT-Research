"use client";

import { Info } from "lucide-react";
import { PanelCloseButton } from "@/components/viewer/PanelDock";
import { Button } from "@/components/ui/button";
import { useSceneObjectStore } from "@/stores/scene-object-store";
import { useViewerStore } from "@/stores/viewer-store";

export function ObjectInspector() {
  const {
    selectedObject,
    setInspectorPanelOpen,
    status,
    flyToSelectedBuilding,
    setCameraPreset,
  } = useViewerStore();
  const sceneObjects = useSceneObjectStore((s) => s.objects);
  const updateObject = useSceneObjectStore((s) => s.updateObject);

  return (
    <aside className="flex w-80 shrink-0 flex-col border-l border-slate-800 bg-slate-950/90 backdrop-blur">
      <div className="flex items-center gap-2 border-b border-slate-800 px-4 py-3">
        <Info className="h-4 w-4 text-sky-400" />
        <h2 className="text-sm font-semibold text-slate-100">Object inspector</h2>
        <PanelCloseButton
          side="right"
          label="object inspector"
          onClose={() => setInspectorPanelOpen(false)}
        />
      </div>
      <div className="flex-1 space-y-4 overflow-y-auto p-4 text-xs text-slate-300">
        <section>
          <h3 className="mb-2 font-semibold text-slate-200">Interaction</h3>
          {status.pickedCoordinate && (
            <p className="text-slate-400">
              Picked: {status.pickedCoordinate.latitude.toFixed(6)},{" "}
              {status.pickedCoordinate.longitude.toFixed(6)} ·{" "}
              {status.pickedCoordinate.height_m.toFixed(1)} m
            </p>
          )}
          {status.measuredDistance_m != null && (
            <p className="text-slate-400">Measured distance: {status.measuredDistance_m.toFixed(2)} m</p>
          )}
        </section>

        {!selectedObject ? (
          <p className="text-slate-500">
            Click a building footprint (GDT layer) or a labeled demo simulation object in the 3D view.
            Use camera presets for aerial, oblique, and street-level navigation.
          </p>
        ) : (
          <section>
            <dl className="space-y-2">
              <div>
                <dt className="text-slate-500">Type</dt>
                <dd className="text-slate-100">{selectedObject.kind}</dd>
              </div>
              <div>
                <dt className="text-slate-500">Identifier</dt>
                <dd className="font-mono text-slate-100">{selectedObject.id}</dd>
              </div>
              {selectedObject.label && (
                <div>
                  <dt className="text-slate-500">Name</dt>
                  <dd>{selectedObject.label}</dd>
                </div>
              )}
              {selectedObject.latitude != null && selectedObject.longitude != null && (
                <div>
                  <dt className="text-slate-500">Coordinates</dt>
                  <dd>
                    {selectedObject.latitude.toFixed(6)}, {selectedObject.longitude.toFixed(6)}
                  </dd>
                </div>
              )}
              {selectedObject.height_m != null && (
                <div>
                  <dt className="text-slate-500">Height (m)</dt>
                  <dd>{selectedObject.height_m.toFixed(2)}</dd>
                </div>
              )}
              {selectedObject.footprint_area_m2 != null && (
                <div>
                  <dt className="text-slate-500">Footprint area (m²)</dt>
                  <dd>{selectedObject.footprint_area_m2.toFixed(1)}</dd>
                </div>
              )}
              {selectedObject.data_source && (
                <div>
                  <dt className="text-slate-500">Data source</dt>
                  <dd>{selectedObject.data_source}</dd>
                </div>
              )}
              {selectedObject.quality && (
                <div>
                  <dt className="text-slate-500">Height / quality</dt>
                  <dd>{selectedObject.quality}</dd>
                </div>
              )}
            </dl>
            {selectedObject.kind === "building" && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button type="button" size="sm" variant="secondary" onClick={() => flyToSelectedBuilding()}>
                  Orbit / close-up
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setCameraPreset("street_level")}
                >
                  Street level
                </Button>
              </div>
            )}
          </section>
        )}

        <section>
          <h3 className="mb-2 font-semibold text-slate-200">Demo simulation objects</h3>
          <p className="mb-2 text-[11px] text-slate-500">
            Not real Galveston infrastructure — for future UAV/sensor experiments.
          </p>
          <ul className="space-y-3">
            {sceneObjects.map((obj) => (
              <li key={obj.id} className="rounded border border-slate-800 p-2">
                <p className="font-medium text-slate-200">{obj.label}</p>
                <label className="mt-2 flex items-center justify-between gap-2">
                  <span>Height (m)</span>
                  <input
                    type="number"
                    className="w-24 rounded border border-slate-700 bg-slate-900 px-1 py-0.5"
                    value={obj.height_m}
                    step={1}
                    onChange={(e) =>
                      updateObject(obj.id, { height_m: Number(e.target.value) || 0 })
                    }
                  />
                </label>
                <label className="mt-1 flex items-center justify-between gap-2">
                  <span>Heading (°)</span>
                  <input
                    type="number"
                    className="w-24 rounded border border-slate-700 bg-slate-900 px-1 py-0.5"
                    value={obj.heading_deg}
                    step={5}
                    onChange={(e) =>
                      updateObject(obj.id, { heading_deg: Number(e.target.value) || 0 })
                    }
                  />
                </label>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </aside>
  );
}
