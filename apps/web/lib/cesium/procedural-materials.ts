/** Procedural massing colors for Galveston stock. Not photographed facades. */

function shift(
  Cesium: typeof import("cesium"),
  rgb: [number, number, number],
  salt: number,
  spread: number,
  alpha: number,
): import("cesium").Color {
  const delta = ((salt % 17) - 8) * spread;
  const clamp = (n: number) => Math.max(0, Math.min(255, Math.round(n + delta)));
  return Cesium.Color.fromBytes(clamp(rgb[0]), clamp(rgb[1]), clamp(rgb[2]), alpha);
}

export function facadeColor(
  Cesium: typeof import("cesium"),
  materialKey: string,
  salt = 0,
): import("cesium").Color {
  const key = materialKey.toLowerCase();
  if (key.includes("brick")) return shift(Cesium, [158, 86, 68], salt, 1.6, 242);
  if (key.includes("stone")) return shift(Cesium, [168, 160, 148], salt, 1.2, 242);
  if (key.includes("masonry")) return shift(Cesium, [186, 176, 160], salt, 1.3, 242);
  if (key.includes("metal")) return shift(Cesium, [176, 180, 184], salt, 1.1, 236);
  if (key.includes("concrete")) return shift(Cesium, [168, 166, 160], salt, 1.0, 236);
  if (key.includes("glass")) return shift(Cesium, [126, 142, 154], salt, 1.2, 210);
  if (key.includes("wood")) return shift(Cesium, [196, 168, 132], salt, 1.5, 242);
  if (key.includes("clapboard")) return shift(Cesium, [214, 206, 190], salt, 1.4, 242);
  return shift(Cesium, [206, 196, 178], salt, 1.4, 242);
}

export function roofColor(
  Cesium: typeof import("cesium"),
  materialKey: string,
  salt = 0,
): import("cesium").Color {
  const key = materialKey.toLowerCase();
  if (key.includes("metal")) return shift(Cesium, [132, 140, 146], salt, 1.1, 250);
  if (key.includes("membrane") || key.includes("flat")) {
    return shift(Cesium, [78, 80, 82], salt, 0.8, 250);
  }
  if (key.includes("asphalt") || key.includes("shingle")) {
    return shift(Cesium, [72, 68, 64], salt, 1.0, 250);
  }
  return shift(Cesium, [84, 80, 74], salt, 1.0, 250);
}
