"use client";

import { Info, Layers3, PanelLeft, PanelRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useViewerStore } from "@/stores/viewer-store";

export function PanelDock() {
  const {
    layersPanelOpen,
    inspectorPanelOpen,
    setLayersPanelOpen,
    setInspectorPanelOpen,
  } = useViewerStore();

  return (
    <>
      {!layersPanelOpen && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="absolute left-3 top-3 z-30 shadow-lg"
          onClick={() => setLayersPanelOpen(true)}
          aria-label="Show layers panel"
        >
          <Layers3 className="mr-1 h-4 w-4" />
          Layers
        </Button>
      )}
      {!inspectorPanelOpen && (
        <Button
          type="button"
          variant="secondary"
          size="sm"
          className="absolute right-3 top-3 z-30 shadow-lg"
          onClick={() => setInspectorPanelOpen(true)}
          aria-label="Show object inspector"
        >
          <Info className="mr-1 h-4 w-4" />
          Inspector
        </Button>
      )}
    </>
  );
}

export function PanelCloseButton({
  side,
  onClose,
  label,
}: {
  side: "left" | "right";
  onClose: () => void;
  label: string;
}) {
  const Icon = side === "left" ? PanelLeft : PanelRight;
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="ml-auto h-8 w-8 shrink-0 text-slate-400 hover:text-slate-100"
      onClick={onClose}
      aria-label={`Hide ${label}`}
      title={`Hide ${label}`}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}
