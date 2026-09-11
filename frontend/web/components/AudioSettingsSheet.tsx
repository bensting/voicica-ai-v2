"use client";

import { useEffect, useState } from "react";
import { AUDIO_SETTINGS_RANGE, getPitchLabel, type AudioSettings } from "@/lib/audio-settings";

type Tab = "speed" | "volume" | "pitch";

const TABS: { id: Tab; icon: React.ReactNode }[] = [
  {
    id: "speed",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
  {
    id: "volume",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
        <path d="M19.07 4.93a10 10 0 010 14.14M15.54 8.46a5 5 0 010 7.07" />
      </svg>
    ),
  },
  {
    id: "pitch",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
      </svg>
    ),
  },
];

const TAB_META: Record<Tab, { title: string; description: string }> = {
  speed: { title: "Speed", description: "How fast the voice talks." },
  volume: { title: "Volume", description: "How loud the voice is." },
  pitch: { title: "Pitch", description: "How deep or bright the voice sounds." },
};

/** Speed/Volume/Pitch — same 3-tab, one-slider-at-a-time layout as the
 * prior project's native TTS page, restyled to this project's tokens.
 * Edits are local until Save; closing without saving discards them. */
export function AudioSettingsSheet({
  isOpen,
  onClose,
  settings,
  onSave,
}: {
  isOpen: boolean;
  onClose: () => void;
  settings: AudioSettings;
  onSave: (settings: AudioSettings) => void;
}) {
  const [tab, setTab] = useState<Tab>("speed");
  // Seeded from `settings` at construction time, not synced via an effect —
  // the parent remounts this component (key={isOpen}) on every open, so a
  // fresh `draft` starting at the last-saved settings is just this state's
  // normal initial value, not something that needs re-syncing later.
  const [draft, setDraft] = useState<AudioSettings>(settings);

  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const range = AUDIO_SETTINGS_RANGE[tab];

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="fixed left-0 right-0 bottom-0 z-50 rounded-t-3xl bg-sheet border-t border-border-soft animate-slide-up"
        style={{ paddingBottom: "calc(env(safe-area-inset-bottom, 0px) + 16px)" }}
      >
        <div className="mx-auto w-full max-w-md">
          <div className="flex items-center justify-between border-b border-border-soft px-4 pt-4 pb-3">
            <div className="flex gap-2">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={`flex h-9 w-9 items-center justify-center rounded-xl transition-colors ${
                    tab === t.id ? "bg-a3/20 text-a3" : "bg-surface text-text-2"
                  }`}
                >
                  {t.icon}
                </button>
              ))}
            </div>
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

          <div className="px-5 pt-5 pb-2">
            <h3 className="font-display font-bold text-lg">{TAB_META[tab].title}</h3>
            <p className="mt-0.5 text-sm text-text-2">{TAB_META[tab].description}</p>
          </div>

          <div className="px-5 pb-2 text-center">
            <span className="inline-block rounded-xl bg-surface px-5 py-2.5 text-xl font-bold tabular-nums">
              {tab === "speed" ? `${draft.speed.toFixed(1)}x` : tab === "volume" ? `${draft.volume}%` : draft.pitch}
            </span>
          </div>

          <div className="px-5 pb-1 pt-3">
            <input
              type="range"
              min={range.min}
              max={range.max}
              step={range.step}
              value={draft[tab]}
              onChange={(e) =>
                setDraft({ ...draft, [tab]: tab === "speed" ? parseFloat(e.target.value) : parseInt(e.target.value, 10) })
              }
              className="w-full accent-[color:var(--a3)]"
            />
            <div className="mt-1.5 flex justify-between text-xs text-text-3">
              <span>{tab === "speed" ? `${range.min}x` : range.min}</span>
              <span>{tab === "speed" ? `${range.max}x` : range.max}</span>
            </div>
            {tab === "pitch" && (
              <p className="mt-2 text-center text-sm font-medium text-text-2">{getPitchLabel(draft.pitch)}</p>
            )}
          </div>

          <div className="px-5 pt-4">
            <button
              onClick={() => {
                onSave(draft);
                onClose();
              }}
              className="grad-bg w-full rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c]"
            >
              Save
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
