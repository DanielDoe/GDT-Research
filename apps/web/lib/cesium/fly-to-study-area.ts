import { presetToFlyOptions } from "@/lib/cesium-camera";
import { cameraPresets, localOrigin, type CameraPresetKey } from "@/lib/study-area";

export function applyCameraPreset(
  viewer: import("cesium").Viewer,
  Cesium: typeof import("cesium"),
  presetKey: CameraPresetKey = "downtown_3d",
) {
  const preset = cameraPresets[presetKey] ?? cameraPresets.study_area;
  if (!preset) {
    viewer.camera.setView({
      destination: Cesium.Cartesian3.fromDegrees(
        localOrigin.longitude,
        localOrigin.latitude,
        320,
      ),
      orientation: {
        heading: Cesium.Math.toRadians(48),
        pitch: Cesium.Math.toRadians(-36),
        roll: 0,
      },
    });
  } else {
    viewer.camera.setView(presetToFlyOptions(preset, Cesium));
  }
  viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
  viewer.scene.requestRender();
}
