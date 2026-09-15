import type { MetadataRoute } from "next";
import { buildMarketingAlternates, buildMarketingUrl } from "@/lib/marketing-seo";

/** Only `(marketing)`'s pages belong here — `(app)`/`/login` are never
 * crawled (ADR 0013), so listing them would just be noise search engines
 * are told to ignore anyway (see `robots.ts`'s `disallow`). Mirrors the
 * fixed page list ADR 0019 shipped; a future page just adds a row here.
 * `alternates.languages` reuses the same locale registry as every other
 * piece of marketing SEO metadata (`lib/marketing-seo.ts`) — today that's
 * just `en`, so each entry points at itself until a real translation adds
 * a row to `MARKETING_LOCALES`. */
const MARKETING_PAGES: { path: string; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"]; priority: number }[] = [
  { path: "", changeFrequency: "weekly", priority: 1 },
  { path: "voice", changeFrequency: "monthly", priority: 0.8 },
  { path: "image", changeFrequency: "monthly", priority: 0.8 },
  { path: "video", changeFrequency: "monthly", priority: 0.8 },
  { path: "contact", changeFrequency: "yearly", priority: 0.3 },
  { path: "privacy", changeFrequency: "yearly", priority: 0.2 },
  { path: "terms", changeFrequency: "yearly", priority: 0.2 },
];

// A fixed date, not `new Date()` — this content hasn't changed since it was
// written; recomputing "now" on every build would claim a freshness that
// isn't real. Bump this by hand when a page's content actually changes.
const LAST_UPDATED = new Date("2026-09-14");

export default function sitemap(): MetadataRoute.Sitemap {
  return MARKETING_PAGES.map(({ path, changeFrequency, priority }) => ({
    url: buildMarketingUrl("", path),
    lastModified: LAST_UPDATED,
    changeFrequency,
    priority,
    alternates: { languages: buildMarketingAlternates(path) },
  }));
}
