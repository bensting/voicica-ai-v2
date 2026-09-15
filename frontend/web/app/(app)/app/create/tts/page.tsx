"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, type Voice } from "@/lib/api";
import { MenuIcon } from "@/components/icons";
import { VoiceSheet } from "@/components/VoiceSheet";
import { AudioSettingsSheet } from "@/components/AudioSettingsSheet";
import { friendlyVoiceName, localeDisplayName } from "@/lib/locale-names";
import { useAudioSettings } from "@/lib/audio-settings";
import { useJobEvents } from "@/lib/job-events";
import { useToast } from "@/components/Toast";

const MAX_CHARS = 500;

export default function CreateTtsPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voice, setVoice] = useState<Voice | null>(null);
  const [voiceSheetOpen, setVoiceSheetOpen] = useState(false);
  const { settings: audioSettings, updateSettings: updateAudioSettings } = useAudioSettings();
  const [audioSheetOpen, setAudioSheetOpen] = useState(false);
  const [shareToExplore, setShareToExplore] = useState(false);
  const { registerPendingJob } = useJobEvents();
  const { show } = useToast();

  // ADR 0018: submit, then get out of the way — this used to block on
  // `pollJob()` right here, showing "Generating…" for as long as the
  // provider took. Every capability behaves the same way now, TTS
  // included, even though TTS itself is usually fast: submit, a toast,
  // the form stays usable immediately. `/app/me` is where "is it done
  // yet" actually gets answered — live, via the SSE push this registers
  // with (`registerPendingJob`), not by this page waiting around.
  async function handleGenerate() {
    // A voice is required — Fish Audio isn't a general fallback, it's
    // reserved for a user's own cloned voices (a separate, not-yet-built
    // slice), so there's no sensible default to fall back to silently.
    if (!text.trim() || !voice) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.submitTts(text.trim(), { voiceId: voice.id }, {
        ...audioSettings,
        visibility: shareToExplore ? "public" : "private",
      });
      registerPendingJob();
      show("Submitted — we'll let you know when it's ready.", { tone: "success", href: "/app/me" });
      // Deliberately not cleared — trying a variation of the same script
      // (different voice/settings) is a common next move, and there's no
      // "result" to navigate away to here anymore.
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center gap-3 px-4 pb-3.5 pt-[18px]">
        <button
          onClick={() => router.back()}
          className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-border-soft bg-surface"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text)" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <span className="font-display font-bold text-[16px]">Text to Speech</span>
      </header>

      <div className="flex-1 px-4 pb-48">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-2">Script</span>
        </div>
        <div className="rounded-2xl border border-border-soft bg-surface p-3.5">
          <textarea
            rows={7}
            maxLength={MAX_CHARS}
            value={text}
            onChange={(e) => setText(e.target.value)}
            disabled={submitting}
            placeholder="Type or paste the text you want narrated…"
            className="w-full resize-none bg-transparent text-[14.5px] leading-relaxed outline-none placeholder:text-text-3"
          />
          <div className="mt-1.5 flex justify-end">
            <span className="text-[11px] text-text-3 tabular-nums">
              {text.length} / {MAX_CHARS}
            </span>
          </div>
        </div>

        {error && (
          <div className="mt-3 rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}

        <button
          onClick={() => setVoiceSheetOpen(true)}
          disabled={submitting}
          className="mt-3 flex w-full items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
        >
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-2">
            <MenuIcon name="mic" width={16} height={16} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13.5px] font-medium">
              {voice ? friendlyVoiceName(voice) : "Select a voice"}
            </div>
            <div className="mt-0.5 truncate text-[11.5px] text-text-2">
              {voice ? localeDisplayName(voice.locale) : "Required"}
            </div>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" className="shrink-0">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>

        <button
          onClick={() => setAudioSheetOpen(true)}
          disabled={submitting}
          className="mt-2.5 flex w-full items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
        >
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13.5px] font-medium">Audio Settings</div>
            <div className="mt-0.5 truncate text-[11.5px] text-text-2">
              Speed {audioSettings.speed.toFixed(1)}x · Volume {audioSettings.volume}% · Pitch {audioSettings.pitch}
            </div>
          </div>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" className="shrink-0">
            <path d="M9 18l6-6-6-6" />
          </svg>
        </button>

        <button
          onClick={() => setShareToExplore((v) => !v)}
          disabled={submitting}
          className="mt-2.5 flex w-full items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
        >
          <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[10px] bg-a3/15 text-a3">
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="12" cy="12" r="9" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <path d="M12 3a15 15 0 010 18M12 3a15 15 0 000 18" />
            </svg>
          </div>
          <div className="flex-1">
            <div className="text-[13.5px] font-semibold">Share to Explore</div>
            <div className="mt-px text-[11.5px] text-text-2">Visible to everyone, no login required to view</div>
          </div>
          <div className={`h-[26px] w-11 flex-shrink-0 rounded-full transition-colors ${shareToExplore ? "grad-bg" : "bg-surface-2 border border-border"}`}>
            <div
              className="h-[21px] w-[21px] rounded-full bg-white shadow transition-transform"
              style={{ transform: shareToExplore ? "translate(20px, 2.5px)" : "translate(2.5px, 2.5px)" }}
            />
          </div>
        </button>
      </div>

      <VoiceSheet
        isOpen={voiceSheetOpen}
        onClose={() => setVoiceSheetOpen(false)}
        onSelect={setVoice}
      />

      <AudioSettingsSheet
        key={audioSheetOpen ? "open" : "closed"}
        isOpen={audioSheetOpen}
        onClose={() => setAudioSheetOpen(false)}
        settings={audioSettings}
        onSave={updateAudioSettings}
      />

      {/* `bottom` matches `BottomNav`'s own real height (`h-16` + its own
       * `env(safe-area-inset-bottom)` padding) instead of a bare `bottom-16` —
       * on a phone with a home indicator, the nav grows taller than 64px, so
       * a bar pinned at exactly 64px from the true viewport edge sat *behind*
       * the now-taller nav (real bug, caught on a real phone) instead of
       * sitting just above it. */}
      <div
        className="fixed left-0 right-0 px-4 pb-4 pt-3"
        style={{
          bottom: "calc(4rem + env(safe-area-inset-bottom, 0px))",
          background: "linear-gradient(0deg, var(--bg) 65%, transparent)",
        }}
      >
        <button
          onClick={handleGenerate}
          disabled={submitting || !text.trim() || !voice}
          className="grad-bg flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c] disabled:opacity-50"
        >
          {submitting ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#120a1c]/30 border-t-[#120a1c]" />
              Submitting…
            </>
          ) : (
            "Generate speech"
          )}
        </button>
      </div>
    </div>
  );
}

// The old inline "Your speech is ready" result screen (audio player +
// public/private toggle) is gone from here — ADR 0018 means this page
// never waits for a result to show one. That same audio-player-plus-
// visibility-toggle pattern now lives on `/app/me`'s own job card, the one
// place results are actually viewed.
