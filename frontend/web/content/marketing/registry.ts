import type { MarketingContent } from "./types";
import { en } from "./en";

/** Every marketing locale actually shipped, keyed by URL slug (`""` = the
 * unprefixed default). Only `en` exists (ADR 0019) — `/th`, `/id`, `/es`
 * intentionally 404 rather than serving a machine-translated stand-in.
 * Adding a language later is: write `content/marketing/th.ts` against
 * `./types.ts`'s shape, add one row here. Nothing else in this file, or in
 * `lib/marketing-seo.ts`, needs to change. */
export const MARKETING_LOCALES: {
  /** URL path segment. Empty string = no prefix (the default locale). */
  slug: string;
  /** BCP-47-ish tag used for <html lang>, hreflang, and OG locale. */
  code: string;
  content: MarketingContent;
}[] = [{ slug: "", code: "en", content: en }];

export const DEFAULT_MARKETING_CONTENT = en;
