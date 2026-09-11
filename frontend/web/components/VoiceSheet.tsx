"use client";

import { useEffect, useMemo, useState } from "react";
import { api, type Voice } from "@/lib/api";
import { friendlyVoiceName, localeDisplayName } from "@/lib/locale-names";

const PROVIDER_LABELS: Record<string, string> = { azure: "Azure", google: "Google", fish_audio: "Fish Audio" };

/** The "Select a voice" picker — GET /catalog/voices already comes back
 * scoped to the target market (services/voice_catalog.py), so this just
 * searches/filters what it's given; no locale allowlist duplicated here. */
export function VoiceSheet({
  isOpen,
  onClose,
  onSelect,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSelect: (voice: Voice) => void;
}) {
  const [voices, setVoices] = useState<Voice[] | null>(null);
  const [search, setSearch] = useState("");
  const [locale, setLocale] = useState("all");
  const [gender, setGender] = useState("all");
  const [provider, setProvider] = useState("all");

  useEffect(() => {
    if (isOpen && voices === null) {
      api.getVoices().then(setVoices).catch(() => setVoices([]));
    }
  }, [isOpen, voices]);

  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  const locales = useMemo(() => {
    if (!voices) return [];
    return Array.from(new Set(voices.map((v) => v.locale))).sort();
  }, [voices]);

  const providers = useMemo(() => {
    if (!voices) return [];
    return Array.from(new Set(voices.map((v) => v.provider))).sort();
  }, [voices]);

  const filtered = useMemo(() => {
    if (!voices) return [];
    const q = search.trim().toLowerCase();
    return voices.filter((v) => {
      if (locale !== "all" && v.locale !== locale) return false;
      if (gender !== "all" && v.gender !== gender) return false;
      if (provider !== "all" && v.provider !== provider) return false;
      if (q && !friendlyVoiceName(v).toLowerCase().includes(q)) return false;
      return true;
    });
  }, [voices, search, locale, gender, provider]);

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

          <div className="flex gap-2 overflow-x-auto px-4 pb-3">
            <select
              value={locale}
              onChange={(e) => setLocale(e.target.value)}
              className="shrink-0 rounded-lg border border-border-soft bg-surface px-2.5 py-1.5 text-xs text-text"
            >
              <option value="all">All languages</option>
              {locales.map((l) => (
                <option key={l} value={l}>
                  {localeDisplayName(l)}
                </option>
              ))}
            </select>
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
            {voices === null && (
              <div className="flex justify-center py-10">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
              </div>
            )}
            {voices && filtered.length === 0 && (
              <p className="py-10 text-center text-sm text-text-2">No voices match.</p>
            )}
            <div className="flex flex-col gap-1.5">
              {filtered.map((v) => (
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
                      {localeDisplayName(v.locale)} · {v.gender ?? "—"} · {PROVIDER_LABELS[v.provider] ?? v.provider}
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
