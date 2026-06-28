import type { NextConfig } from "next";

const dashboardUrl =
  process.env.NEXT_PUBLIC_DASHBOARD_URL?.replace(/\/+$/, "") ||
  "https://app.owlbell.xyz";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/dashboard",
        destination: `${dashboardUrl}/dashboard`,
        permanent: false,
      },
      {
        source: "/dashboard/:path*",
        destination: `${dashboardUrl}/dashboard/:path*`,
        permanent: false,
      },
    ];
  },
};

export default nextConfig;