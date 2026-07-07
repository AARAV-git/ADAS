import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  /* config options here */
  typescript: {
    ignoreBuildErrors: true,
  },
  reactStrictMode: false,
  allowedDevOrigins: ["192.168.31.142", "192.168.31.142:3000", "localhost:3000"],
} as any; // Typecast to any in case types haven't caught up with latest version

export default nextConfig;
