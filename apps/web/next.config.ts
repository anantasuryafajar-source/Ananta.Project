import type { NextConfig } from "next";

const config: NextConfig = {
  // Turbopack default di Next 16. Proxy /api ke FastAPI saat dev.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.API_BASE ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default config;
