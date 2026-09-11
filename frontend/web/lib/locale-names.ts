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

/** Formats a BCP-47 locale code ("es-MX") as a human-readable name
 * ("Spanish (Mexico)") using the browser's own Intl.DisplayNames — no
 * lookup table to maintain, works for any locale the backend ever sends,
 * not just the target market's ~24 (the zero-frontend-config principle
 * applied literally: not even a small reference table needed here). */
export function localeDisplayName(code: string): string {
  const [language, region] = code.split("-");
  try {
    const languageName = new Intl.DisplayNames(["en"], { type: "language" }).of(language);
    const regionName = region
      ? new Intl.DisplayNames(["en"], { type: "region" }).of(region)
      : undefined;
    return regionName ? `${languageName} (${regionName})` : (languageName ?? code);
  } catch {
    return code;
  }
}
