import type { Voice } from "./api";

/** Google's voice list has no separate human name — display_name is the raw
 * voice id ("th-TH-Chirp3-HD-Achernar"). Azure's own DisplayName never has
 * this shape, so stripping the leading "{locale}-" is safe and only ever
 * changes how a Google row reads, never the id sent to generate speech. */
export function friendlyVoiceName(voice: Voice): string {
  const prefix = `${voice.locale}-`;
  return voice.display_name.startsWith(prefix)
    ? voice.display_name.slice(prefix.length).replace(/-/g, " ")
    : voice.display_name;
}

function safeDisplayName(type: "language" | "region" | "script", value: string): string | undefined {
  try {
    return new Intl.DisplayNames(["en"], { type }).of(value) ?? undefined;
  } catch {
    return undefined;
  }
}

// A real BCP-47 script subtag is exactly 4 letters, title-cased ("Latn",
// "Cans") — distinct from a 2-letter region ("CN") or a lowercase dialect
// word Azure invents for some of its locale codes ("guangxi").
const SCRIPT_SUBTAG = /^[A-Z][a-z]{3}$/;

/** Formats a BCP-47(-ish) locale code as a human-readable name using the
 * browser's own Intl.DisplayNames — no lookup table to maintain, works for
 * any locale the backend ever sends. Most codes are just "{language}-{REGION}"
 * ("es-MX" -> "Spanish (Mexico)"), but a handful of real, synced Azure
 * locales have a third segment that isn't a region at all: a script subtag
 * ("sr-Latn-RS", "iu-Cans-CA") or one of Azure's own dialect labels
 * ("zh-CN-guangxi", "zh-CN-henan", ...) — treating that segment as the
 * region (the naive `code.split("-")[1]` approach) silently drops it,
 * making every zh-CN-* dialect display as the identical "Chinese (China)". */
export function localeDisplayName(code: string): string {
  const [language, second, third] = code.split("-");
  const languageName = safeDisplayName("language", language) ?? code;
  if (!second) return languageName;

  const isScript = SCRIPT_SUBTAG.test(second);
  const region = isScript ? third : second;
  const dialect = isScript ? undefined : third; // e.g. "guangxi" — not real BCP-47, just Azure's own label

  const descriptors = [
    isScript ? safeDisplayName("script", second) : undefined,
    dialect ? dialect.charAt(0).toUpperCase() + dialect.slice(1) : undefined,
    region ? safeDisplayName("region", region) : undefined,
  ].filter((d): d is string => !!d);

  return descriptors.length ? `${languageName} (${descriptors.join(", ")})` : languageName;
}
