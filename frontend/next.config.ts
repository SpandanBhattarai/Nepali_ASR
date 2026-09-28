import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  allowedDevOrigins : ["192.168.10.61", "192.168.10.*"],
};

export default nextConfig;
