export function configureCameraNavigation(viewer: import("cesium").Viewer) {
  const controller = viewer.scene.screenSpaceCameraController;
  controller.enableCollisionDetection = true;
  controller.enableLook = true;
  controller.enableRotate = true;
  controller.enableTilt = true;
  controller.enableTranslate = true;
  controller.enableZoom = true;
  controller.inertiaSpin = 0.85;
  controller.inertiaTranslate = 0.85;
  controller.inertiaZoom = 0.75;
  controller.minimumZoomDistance = 1.5;
  controller.maximumZoomDistance = 50_000_000;
  controller.bounceAnimationTime = 0.25;
  controller.minimumCollisionTerrainHeight = 2;
}

export function configureSceneVisuals(
  viewer: import("cesium").Viewer,
  options?: { realisticLighting?: boolean },
) {
  const { scene } = viewer;
  const realistic = options?.realisticLighting ?? true;
  scene.globe.depthTestAgainstTerrain = true;
  scene.globe.enableLighting = realistic;
  scene.globe.maximumScreenSpaceError = 1.5;
  scene.fog.enabled = true;
  scene.fog.density = realistic ? 0.00006 : 0.00008;
  scene.skyAtmosphere.show = true;
  scene.sun.show = true;
  scene.moon.show = false;
  if (scene.skyBox) {
    scene.skyBox.show = true;
  }
  viewer.shadows = realistic;
}
