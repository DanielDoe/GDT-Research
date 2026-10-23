import type { NextConfig } from "next";
import path from "path";
import CopyWebpackPlugin from "copy-webpack-plugin";
import webpack from "webpack";

const cesiumSource = path.join(__dirname, "node_modules", "cesium", "Build", "Cesium");
const cesiumBaseUrl = "cesium";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["cesium"],
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.plugins.push(
        new CopyWebpackPlugin({
          patterns: [
            { from: path.join(cesiumSource, "Workers"), to: path.join("..", "public", cesiumBaseUrl, "Workers") },
            { from: path.join(cesiumSource, "ThirdParty"), to: path.join("..", "public", cesiumBaseUrl, "ThirdParty") },
            { from: path.join(cesiumSource, "Assets"), to: path.join("..", "public", cesiumBaseUrl, "Assets") },
            { from: path.join(cesiumSource, "Widgets"), to: path.join("..", "public", cesiumBaseUrl, "Widgets") },
          ],
        }),
      );
    }

    config.resolve.alias = {
      ...config.resolve.alias,
      cesium: path.join(__dirname, "node_modules", "cesium"),
      "@zip.js/zip.js/lib/zip-no-worker.js": path.join(
        __dirname,
        "node_modules",
        "@zip.js",
        "zip.js",
        "lib",
        "zip-no-worker.js",
      ),
    };

    config.plugins.push(
      new webpack.DefinePlugin({
        CESIUM_BASE_URL: JSON.stringify(`/${cesiumBaseUrl}`),
      }),
    );

    config.ignoreWarnings = [/Failed to parse source map/];

    return config;
  },
};

export default nextConfig;
