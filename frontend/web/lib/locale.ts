"use client";

/** The (app) surface's locale preference — a plain cookie, not a URL prefix
 * ([ADR 0013](../../docs/decisions/0013-i18n-routing-strategy.md):
 * `(marketing)` gets locale-prefixed URLs for SEO, `(app)` is never crawled
 * so a stored preference is enough). Nothing writes this cookie yet — the
 * top-left language switcher isn't built — so everyone reads the "en"
 * fallback for now; the plumbing doesn't need to wait on that. */

const COOKIE_NAME = "voicica_locale";
const SUPPORTED = ["en", "th", "id", "es"] as const;

export type Locale = (typeof SUPPORTED)[number];

export function getLocale(): Locale {
  if (typeof document === "undefined") return "en";
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE_NAME}=([^;]*)`));
  const value = match ? decodeURIComponent(match[1]) : null;
  return (SUPPORTED as readonly string[]).includes(value ?? "") ? (value as Locale) : "en";
}

export function setLocale(locale: Locale) {
  document.cookie = `${COOKIE_NAME}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
}
