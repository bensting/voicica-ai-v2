import { MARKETING_LOCALES } from "@/content/marketing/registry";

/** No production domain is decided yet — this env var is unset in local
 * dev on purpose (falls back to localhost) and must be set to the real
 * domain once one exists, so canonical/OG URLs aren't silently wrong. */
export const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

/** Builds an absolute marketing URL for a given locale slug + path, mirroring
 * the prior project's `buildSeoUrl` convention (`config/seo/locales.ts`):
 * the default locale (`slug: ""`) is unprefixed. `path` has no leading
 * slash, e.g. `buildMarketingUrl("", "voice")`. */
export function buildMarketingUrl(slug: string, path: string = ""): string {
  const prefix = slug ? `/${slug}` : "";
  const suffix = path ? `/${path}` : "";
  return `${SITE_URL}${prefix}${suffix}`;
}

/** hreflang alternates for a given path, one entry per *registered* locale
 * (today, just `en`) plus `x-default` pointing at the unprefixed URL —
 * never fabricates an entry for a locale that has no real content (ADR
 * 0019's whole point: no `/th` URL exists until there's real Thai copy). */
export function buildMarketingAlternates(path: string = ""): Record<string, string> {
  const alternates: Record<string, string> = {};
  for (const locale of MARKETING_LOCALES) {
    alternates[locale.code] = buildMarketingUrl(locale.slug, path);
  }
  alternates["x-default"] = buildMarketingUrl("", path);
  return alternates;
}
