import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/marketing-seo";

/** `(app)` is never meant to be crawled (ADR 0013 — authenticated pages,
 * no SEO value) and requires login anyway; disallowing it here just makes
 * that explicit to well-behaved crawlers rather than relying on the auth
 * gate alone. `(marketing)` is the entire point of having a sitemap. */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: ["/app"] }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
