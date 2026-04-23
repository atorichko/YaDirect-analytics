import type { NextConfig } from "next";

const rawBase = process.env.NEXT_PUBLIC_BASE_PATH?.trim() ?? "";
const basePath = rawBase.replace(/\/$/, "");

const nextConfig: NextConfig = {
  reactStrictMode: true,
  basePath: basePath.length > 0 ? basePath : undefined,
};

export default nextConfig;
