import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  // Fetch 1 ID and dry-runs wait for bounded FLAPI calls (including retry).
  experimental: { proxyTimeout: 300_000 },
  // Proxy API calls to the FastAPI backend — same-origin from the
  // browser's point of view, so no CORS setup is needed.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
