import { cpSync, existsSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "node_modules", "cesium", "Build", "Cesium");
const dest = join(root, "public", "cesium");

if (!existsSync(source)) {
  console.warn("[copy-cesium-assets] cesium package not found, skipping");
  process.exit(0);
}

for (const folder of ["Workers", "ThirdParty", "Assets", "Widgets"]) {
  const from = join(source, folder);
  const to = join(dest, folder);
  if (existsSync(to)) {
    rmSync(to, { recursive: true, force: true });
  }
  mkdirSync(dirname(to), { recursive: true });
  cpSync(from, to, { recursive: true });
}

console.log("[copy-cesium-assets] copied Cesium runtime assets to public/cesium");
