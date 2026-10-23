import { useResearchAgentStore } from "@/stores/research-agent-store";
import { useViewerStore } from "@/stores/viewer-store";
import { useWorkspaceStore } from "@/stores/workspace-store";

/** Remove the gauge playback, drop the chosen parameters, and restore the downtown map. */
export function exitResearchScene() {
  useResearchAgentStore.getState().clearResearchScene();
  useWorkspaceStore.getState().setMode("map");
  const viewer = useViewerStore.getState();
  if (viewer.selectedObject?.kind === "observation") {
    viewer.setSelectedObject(null);
  }
  viewer.setCameraPreset("downtown_3d");
}
