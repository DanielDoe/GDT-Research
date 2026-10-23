/**
 * Ground-following first-person navigation for Cesium.
 * Terrain clamp only — not building mesh collision.
 */

export type WalkControllerOptions = {
  moveSpeedMps?: number;
  sprintMultiplier?: number;
  eyeHeightM?: number;
  mouseSensitivity?: number;
};

export class FirstPersonWalkController {
  private viewer: import("cesium").Viewer;
  private Cesium: typeof import("cesium");
  private active = false;
  private keys = new Set<string>();
  private heading = 0;
  private pitch = 0;
  private onKeyDown: (e: KeyboardEvent) => void;
  private onKeyUp: (e: KeyboardEvent) => void;
  private onMouseMove: (e: MouseEvent) => void;
  private removeTick: (() => void) | undefined;
  private lastStepMs = 0;
  private tickListener = () => {
    if (!this.active) return;
    void this.step();
  };
  private opts: Required<WalkControllerOptions>;

  constructor(
    viewer: import("cesium").Viewer,
    Cesium: typeof import("cesium"),
    options?: WalkControllerOptions,
  ) {
    this.viewer = viewer;
    this.Cesium = Cesium;
    this.opts = {
      moveSpeedMps: options?.moveSpeedMps ?? 3.2,
      sprintMultiplier: options?.sprintMultiplier ?? 2.2,
      eyeHeightM: options?.eyeHeightM ?? 1.65,
      mouseSensitivity: options?.mouseSensitivity ?? 0.0022,
    };

    this.onKeyDown = (e) => {
      this.keys.add(e.code);
      if (["KeyW", "KeyA", "KeyS", "KeyD", "Space"].includes(e.code)) {
        e.preventDefault();
      }
    };
    this.onKeyUp = (e) => this.keys.delete(e.code);
    this.onMouseMove = (e) => {
      if (!this.active || e.buttons !== 1) return;
      this.heading -= e.movementX * this.opts.mouseSensitivity;
      this.pitch -= e.movementY * this.opts.mouseSensitivity;
      const limit = this.Cesium.Math.toRadians(88);
      this.pitch = this.Cesium.Math.clamp(this.pitch, -limit, limit);
    };
  }

  start() {
    if (this.active) return;
    this.active = true;
    this.heading = this.viewer.camera.heading;
    this.pitch = this.viewer.camera.pitch;

    this.viewer.scene.screenSpaceCameraController.enableInputs = false;
    window.addEventListener("keydown", this.onKeyDown);
    window.addEventListener("keyup", this.onKeyUp);
    this.viewer.canvas.addEventListener("mousemove", this.onMouseMove);

    this.removeTick = this.viewer.clock.onTick.addEventListener(this.tickListener);
  }

  stop() {
    if (!this.active) return;
    this.active = false;
    this.keys.clear();
    this.viewer.scene.screenSpaceCameraController.enableInputs = true;
    window.removeEventListener("keydown", this.onKeyDown);
    window.removeEventListener("keyup", this.onKeyUp);
    this.viewer.canvas.removeEventListener("mousemove", this.onMouseMove);
    this.removeTick?.();
    this.removeTick = undefined;
  }

  isRunning() {
    return this.active;
  }

  setMoveSpeed(mps: number) {
    this.opts.moveSpeedMps = Math.max(0.5, Math.min(25, mps));
  }

  setEyeHeight(m: number) {
    this.opts.eyeHeightM = Math.max(0.5, Math.min(50, m));
  }

  private async step() {
    const Cesium = this.Cesium;
    const now = performance.now();
    const dt = Math.min(0.05, this.lastStepMs ? (now - this.lastStepMs) / 1000 : 0.016);
    this.lastStepMs = now;
    let speed = this.opts.moveSpeedMps;
    if (this.keys.has("ShiftLeft") || this.keys.has("ShiftRight")) {
      speed *= this.opts.sprintMultiplier;
    }

    let forward = 0;
    let strafe = 0;
    if (this.keys.has("KeyW")) forward += 1;
    if (this.keys.has("KeyS")) forward -= 1;
    if (this.keys.has("KeyD")) strafe += 1;
    if (this.keys.has("KeyA")) strafe -= 1;
    if (forward === 0 && strafe === 0) {
      this.applyOrientation();
      return;
    }

    const distance = speed * dt;
    const camera = this.viewer.camera;
    if (forward > 0) camera.moveForward(forward * distance);
    if (forward < 0) camera.moveBackward(-forward * distance);
    if (strafe > 0) camera.moveRight(strafe * distance);
    if (strafe < 0) camera.moveLeft(-strafe * distance);

    const carto = Cesium.Cartographic.fromCartesian(camera.position);
    try {
      const [updated] = await Cesium.sampleTerrainMostDetailed(
        this.viewer.terrainProvider,
        [carto],
      );
      carto.height = (updated.height ?? 0) + this.opts.eyeHeightM;
    } catch {
      carto.height = (carto.height ?? 0) + this.opts.eyeHeightM;
    }

    camera.setView({
      destination: Cesium.Cartesian3.fromRadians(carto.longitude, carto.latitude, carto.height),
      orientation: {
        heading: this.heading,
        pitch: this.pitch,
        roll: 0,
      },
    });
  }

  private applyOrientation() {
    const Cesium = this.Cesium;
    const camera = this.viewer.camera;
    const carto = Cesium.Cartographic.fromCartesian(camera.position);
    camera.setView({
      destination: Cesium.Cartesian3.fromRadians(
        carto.longitude,
        carto.latitude,
        carto.height,
      ),
      orientation: {
        heading: this.heading,
        pitch: this.pitch,
        roll: 0,
      },
    });
  }
}
