import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next's default image optimizer needs a Node server (or a Cloudflare-
  // specific loader) it doesn't have here — every image this app serves is
  // either a small local static asset (logo, badge) or already-compressed
  // provider output, so there's nothing worth the extra runtime complexity
  // optimizing. Revisit if that changes (e.g. serving large photos direct
  // from R2 through next/image).
  images: { unoptimized: true },
};

export default nextConfig;
