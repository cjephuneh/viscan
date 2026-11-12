import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1"],
  output: "standalone",
  // Hide the floating Next.js “N” badge in the bottom corner during development.
  devIndicators: false,
};

export default nextConfig;
