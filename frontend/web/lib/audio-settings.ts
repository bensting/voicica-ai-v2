"use client";

import { useState } from "react";

/** Speed/volume/pitch — one provider-agnostic scale sent as-is to
 * POST /generate/tts (backend/app/api/schemas.py's TTSRequest); each
 * provider adapter converts to its own units server-side. Ranges/defaults
 * match the prior project's (verified-in-production) AudioSettings type. */
export interface AudioSettings {
  speed: number;
  volume: number;
  pitch: number;
}

export const DEFAULT_AUDIO_SETTINGS: AudioSettings = { speed: 1.0, volume: 50, pitch: 50 };

export const AUDIO_SETTINGS_RANGE = {
  speed: { min: 0.5, max: 2.0, step: 0.1 },
  volume: { min: 1, max: 100, step: 1 },
  pitch: { min: 1, max: 100, step: 1 },
} as const;

export function getPitchLabel(value: number): string {
  if (value <= 10) return "Deep";
  if (value <= 35) return "Dull";
  if (value <= 65) return "Consistent";
  if (value <= 90) return "Bright";
  return "Crisp";
}

const STORAGE_KEY = "tts_audio_settings";

/** A sticky, per-browser preference (like the prior project's), not
 * per-generation state and not synced server-side — reasonable for a
 * "how do I like my voice tuned" setting. localStorage only, so it can
 * come back empty (private window, cleared storage); callers get
 * DEFAULT_AUDIO_SETTINGS in that case, same as a first-time visitor. */
export function useAudioSettings() {
  // Lazy initializer (runs once, during render — not an effect) rather than
  // default-then-sync-in-an-effect: reads localStorage directly on first
  // client render. Guarded for SSR, where window doesn't exist.
  const [settings, setSettings] = useState<AudioSettings>(() => {
    if (typeof window === "undefined") return DEFAULT_AUDIO_SETTINGS;
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return { ...DEFAULT_AUDIO_SETTINGS, ...JSON.parse(saved) };
    } catch {
      // ignore — defaults already set
    }
    return DEFAULT_AUDIO_SETTINGS;
  });

  function updateSettings(next: AudioSettings) {
    setSettings(next);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // best-effort — the in-memory value still applies this session
    }
  }

  function resetSettings() {
    updateSettings(DEFAULT_AUDIO_SETTINGS);
  }

  return { settings, updateSettings, resetSettings };
}
