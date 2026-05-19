import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpackDevMiddleware: (config) => {
    config.watchOptions = { poll: 1000, aggregateTimeout: 300 };
    return config;
  },
  allowedDevOrigins: ["192.168.101.11"],
};

export default nextConfig;
