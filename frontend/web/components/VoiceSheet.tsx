"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type LocaleOption, type Voice } from "@/lib/api";
import { getLocale } from "@/lib/locale";
import { friendlyVoiceName, localeDisplayName } from "@/lib/locale-names";

const PROVIDER_LABELS: Record<string, string> = { azure: "Azure", google: "Google", fish_audio: "Fish Audio" };

/** One representative locale per commonly-picked language, target market
 * first — mirrors the prior project's POPULAR_LANGUAGES shortlist. Every
 * other locale the catalog actually has (158+, all of Azure/Google's
 * coverage — no target-market restriction, backend/README.md) still shows
 * up below, under "All languages"; this only decides what's quick to reach. */
const POPULAR_LOCALES = [
  "th-TH", "id-ID", "es-ES", "es-MX", "en-US",
  "zh-CN", "ja-JP", "ko-KR", "fr-FR", "de-DE",
  "pt-BR", "ru-RU", "ar-SA", "hi-IN", "vi-VN",
];

/** lib/locale.ts's short app-locale cookie ("th") -> a representative
 * BCP-47 voice locale ("th-TH") to preselect the picker with. */
const APP_LOCALE_TO_VOICE_LOCALE: Record<string, string> = {
  th: "th-TH",
  id: "id-ID",
  es: "es-ES",
  en: "en-US",
};

/** The "Select a voice" picker — fetches one language's voices at a time
 * (like the prior project's useVoices() hook), never the whole catalog:
 * GET /catalog/voices covers every language Azure/Google support (2800+
 * voices total), so loading it all up front would be exactly the latency
 * cost the product's own speed priority argues against. */
export function VoiceSheet({
  isOpen,
  onClose,
  onSelect,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (voice: Voice) => void;
}) {
  const [locales, setLocales] = useState<LocaleOption[] | null>(null);
  const [selectedLocale, setSelectedLocale] = useState<string | null>(null);
  const [voices, setVoices] = useState<Voice[] | null>(null);
  const [voicesLocale, setVoicesLocale] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [gender, setGender] = useState("all");
  const [provider, setProvider] = useState("all");

  // Load the language list once, then pick a sensible starting locale.
  useEffect(() => {
    if (isOpen && locales === null) {
      api.getLocales().then((options) => {
        setLocales(options);
        const codes = new Set(options.map((o) => o.locale));
        const preferred = APP_LOCALE_TO_VOICE_LOCALE[getLocale()];
        const fallback = POPULAR_LOCALES.find((l) => codes.has(l)) ?? options[0]?.locale;
        setSelectedLocale((preferred && codes.has(preferred) ? preferred : fallback) ?? null);
      }).catch(() => setLocales([]));
    }
  }, [isOpen, locales]);

  // Fetch that locale's voices whenever it changes. voicesLocale (rather
  // than resetting `voices` to null synchronously, which trips the
  // set-state-in-effect lint rule) is how the render below knows a fetch
  // for the current selection is still in flight.
  useEffect(() => {
    if (!selectedLocale) return;
    let cancelled = false;
    api
      .getVoices(undefined, selectedLocale)
      .then((result) => {
        if (cancelled) return;
        setVoices(result);
        setVoicesLocale(selectedLocale);
      })
      .catch(() => {
        if (cancelled) return;
        setVoices([]);
        setVoicesLocale(selectedLocale);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedLocale]);

  const loadingVoices = selectedLocale !== null && voicesLocale !== selectedLocale;

  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const { popularOptions, otherOptions } = useMemo(() => {
    if (!locales) return { popularOptions: [], otherOptions: [] };
    const byCode = new Map(locales.map((o) => [o.locale, o]));
    const popular = POPULAR_LOCALES.map((l) => byCode.get(l)).filter((o): o is LocaleOption => !!o);
    const popularCodes = new Set(popular.map((o) => o.locale));
    const other = locales.filter((o) => !popularCodes.has(o.locale));
    return { popularOptions: popular, otherOptions: other };
  }, [locales]);

  const providers = useMemo(() => {
    if (!voices) return [];
    return Array.from(new Set(voices.map((v) => v.provider))).sort();
  }, [voices]);

  const filtered = useMemo(() => {
    if (!voices) return [];
    const q = search.trim().toLowerCase();
    return voices.filter((v) => {
      if (gender !== "all" && v.gender !== gender) return false;
      if (provider !== "all" && v.provider !== provider) return false;
      if (q && !friendlyVoiceName(v).toLowerCase().includes(q)) return false;
      return true;
    });
  }, [voices, search, gender, provider]);

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed left-0 right-0 top-[8vh] bottom-0 z-50 rounded-t-3xl bg-sheet border-t border-border-soft animate-slide-up">
        <div className="mx-auto flex h-full w-full max-w-md flex-col overflow-hidden">
          <div className="flex items-center justify-between px-4 pt-4 pb-2">
            <h2 className="font-display font-bold text-lg">Select Voice</h2>
            <button
              onClick={onClose}
              aria-label="Close"
              className="flex h-8 w-8 items-center justify-center rounded-full text-text-2 active:bg-surface-2"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          <div className="px-4 pb-2">
            <div className="flex items-center gap-2 rounded-xl border border-border-soft bg-surface px-3 py-2.5">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" className="shrink-0">
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search voices…"
                className="w-full min-w-0 bg-transparent text-sm outline-none placeholder:text-text-3"
              />
            </div>
          </div>

          <div className="px-4 pb-2">
            <select
              value={selectedLocale ?? ""}
              onChange={(e) => setSelectedLocale(e.target.value)}
              disabled={!locales}
              className="w-full rounded-xl border border-border-soft bg-surface px-3 py-2.5 text-sm text-text disabled:opacity-60"
            >
              {popularOptions.length > 0 && (
                <optgroup label="Popular">
                  {popularOptions.map((o) => (
                    <option key={o.locale} value={o.locale}>
                      {localeDisplayName(o.locale)}
                    </option>
                  ))}
                </optgroup>
              )}
              {otherOptions.length > 0 && (
                <optgroup label="All languages">
                  {otherOptions.map((o) => (
                    <option key={o.locale} value={o.locale}>
                      {localeDisplayName(o.locale)}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
          </div>

          <div className="flex gap-2 overflow-x-auto px-4 pb-3">
            <select
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              className="shrink-0 rounded-lg border border-border-soft bg-surface px-2.5 py-1.5 text-xs text-text"
            >
              <option value="all">Any gender</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
            </select>
            {providers.length > 1 && (
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
                className="shrink-0 rounded-lg border border-border-soft bg-surface px-2.5 py-1.5 text-xs text-text"
              >
                <option value="all">Any provider</option>
                {providers.map((p) => (
                  <option key={p} value={p}>
                    {PROVIDER_LABELS[p] ?? p}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">
            {(locales === null || loadingVoices) && (
              <div className="flex justify-center py-10">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
              </div>
            )}
            {!loadingVoices && voices && filtered.length === 0 && (
              <p className="py-10 text-center text-sm text-text-2">No voices match.</p>
            )}
            <div className="flex flex-col gap-1.5">
              {!loadingVoices && filtered.map((v) => (
                <button
                  key={v.id}
                  onClick={() => {
                    onSelect(v);
                    onClose();
                  }}
                  className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2.5 text-left active:bg-surface-2"
                >
                  <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-xs font-semibold text-text-2">
                    {friendlyVoiceName(v).slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{friendlyVoiceName(v)}</div>
                    <div className="mt-0.5 truncate text-[11px] text-text-2">
                      {v.gender ?? "—"} · {PROVIDER_LABELS[v.provider] ?? v.provider}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
