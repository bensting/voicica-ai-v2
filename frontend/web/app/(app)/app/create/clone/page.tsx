"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type JobResponse, type VoiceModel } from "@/lib/api";
import { AudioRecorder, type RecordedAudio } from "@/components/AudioRecorder";
import { AudioSettingsSheet } from "@/components/AudioSettingsSheet";
import { useAudioSettings } from "@/lib/audio-settings";

const MAX_CHARS = 500;
type TabId = "generate" | "clone";

/** Voice cloning (ADR 0009) — one page, two tabs, mirroring the prior
 * project's own `/native/create/clone` (CLAUDE.md: "增加一个菜单，然后在一个
 * 页面里完成"). Scoped to a user's *own* cloned voices only — the prior
 * project's Generate tab also let you browse Fish Audio's public voice
 * marketplace (FishVoiceGrid); that's a separate, undocumented feature (no
 * ADR/api-contract.md entry) and out of scope here, matching the actual
 * question this was built for ("客户生成自己的模型 同时用自己的模型来生成语音").
 * Fish Audio only, for now — the only provider this product has a verified
 * cloning integration against (ADR 0009's own open item on Azure/Google). */
export default function VoiceClonePage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("generate");
  const [voiceModels, setVoiceModels] = useState<VoiceModel[] | null>(null);

  async function refreshVoiceModels() {
    try {
      setVoiceModels(await api.listVoiceModels());
    } catch {
      setVoiceModels((current) => current ?? []);
    }
  }

  useEffect(() => {
    api.listVoiceModels().then(setVoiceModels).catch(() => setVoiceModels([]));
  }, []);

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
        <span className="font-display font-bold text-[16px]">Clone Your Voice</span>
      </header>

      <div className="px-4 pb-3">
        <div className="flex rounded-full border border-border-soft bg-surface p-1">
          {(["generate", "clone"] as TabId[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 rounded-full py-2 text-[13px] font-semibold transition-colors ${
                activeTab === tab ? "grad-bg text-[#120a1c]" : "text-text-2"
              }`}
            >
              {tab === "generate" ? "Generate" : "Clone"}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 px-4 pb-48">
        {activeTab === "generate" ? (
          <GenerateTab voiceModels={voiceModels} onGoToClone={() => setActiveTab("clone")} />
        ) : (
          <CloneTab voiceModels={voiceModels} onCloned={refreshVoiceModels} />
        )}
      </div>
    </div>
  );
}

function GenerateTab({
  voiceModels,
  onGoToClone,
}: {
  voiceModels: VoiceModel[] | null;
  onGoToClone: () => void;
}) {
  const [text, setText] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);
  const { settings: audioSettings, updateSettings: updateAudioSettings } = useAudioSettings();
  const [audioSheetOpen, setAudioSheetOpen] = useState(false);
  const [shareToExplore, setShareToExplore] = useState(false);

  async function handleGenerate() {
    if (!text.trim() || !selectedId) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitTts(text.trim(), { voiceModelId: selectedId }, {
        ...audioSettings,
        visibility: shareToExplore ? "public" : "private",
      });
      setJob(result);
      if (result.status === "failed") setError(result.error ?? "Generation failed.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  if (job && job.status === "succeeded") {
    return <ResultView job={job} onCreateAnother={() => { setJob(null); setText(""); }} />;
  }

  return (
    <div>
      <div className="mb-2 flex items-center justify-between pt-1">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-2">Script</span>
      </div>
      <div className="rounded-2xl border border-border-soft bg-surface p-3.5">
        <textarea
          rows={6}
          maxLength={MAX_CHARS}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={submitting}
          placeholder="Type or paste the text you want narrated…"
          className="w-full resize-none bg-transparent text-[14.5px] leading-relaxed outline-none placeholder:text-text-3"
        />
        <div className="mt-1.5 flex justify-end">
          <span className="text-[11px] text-text-3 tabular-nums">{text.length} / {MAX_CHARS}</span>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
          {error}
        </div>
      )}

      <div className="mb-2 mt-4 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-2">Your cloned voices</span>
      </div>

      {voiceModels === null && (
        <div className="flex justify-center py-8">
          <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
        </div>
      )}

      {voiceModels?.length === 0 && (
        <div className="rounded-2xl border border-dashed border-border py-8 text-center">
          <p className="text-sm text-text-2">You haven&apos;t cloned a voice yet.</p>
          <button onClick={onGoToClone} className="mt-2 text-sm font-semibold text-a3">
            Clone one now
          </button>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {voiceModels?.map((vm) => (
          <button
            key={vm.id}
            onClick={() => setSelectedId(vm.id)}
            disabled={submitting}
            className={`flex items-center gap-3 rounded-2xl border px-4 py-3 text-left disabled:opacity-60 ${
              selectedId === vm.id ? "border-a3 bg-a3/10" : "border-border-soft bg-surface"
            }`}
          >
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-2">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                <path d="M19 10v2a7 7 0 01-14 0v-2" />
              </svg>
            </div>
            <div className="min-w-0 flex-1 truncate text-[13.5px] font-medium">{vm.title}</div>
            {selectedId === vm.id && (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--a3)" strokeWidth="2.2">
                <polyline points="20,6 9,17 4,12" />
              </svg>
            )}
          </button>
        ))}
      </div>

      <button
        onClick={() => setAudioSheetOpen(true)}
        disabled={submitting}
        className="mt-3 flex w-full items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
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
            Speed {audioSettings.speed.toFixed(1)}x · Volume {audioSettings.volume}%
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

      <AudioSettingsSheet
        key={audioSheetOpen ? "open" : "closed"}
        isOpen={audioSheetOpen}
        onClose={() => setAudioSheetOpen(false)}
        settings={audioSettings}
        onSave={updateAudioSettings}
      />

      <div className="fixed bottom-16 left-0 right-0 px-4 pb-4 pt-3" style={{ background: "linear-gradient(0deg, var(--bg) 65%, transparent)" }}>
        <button
          onClick={handleGenerate}
          disabled={submitting || !text.trim() || !selectedId}
          className="grad-bg flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c] disabled:opacity-50"
        >
          {submitting ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#120a1c]/30 border-t-[#120a1c]" />
              Generating…
            </>
          ) : (
            "Generate speech"
          )}
        </button>
      </div>
    </div>
  );
}

function CloneTab({
  voiceModels,
  onCloned,
}: {
  voiceModels: VoiceModel[] | null;
  onCloned: () => void;
}) {
  const [audio, setAudio] = useState<RecordedAudio | null>(null);
  const [name, setName] = useState("");
  const [referenceText, setReferenceText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const canClone = audio !== null && name.trim().length > 0 && !submitting;

  async function handleClone() {
    if (!audio || !name.trim()) return;
    setSubmitting(true);
    setError(null);
    setSuccess(false);
    try {
      const job = await api.trainVoiceModel(name.trim(), audio.blob, audio.fileName, referenceText.trim() || undefined);
      if (job.status === "failed") {
        setError(job.error ?? "Cloning failed.");
      } else {
        setSuccess(true);
        setAudio(null);
        setName("");
        setReferenceText("");
        await onCloned();
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await api.deleteVoiceModel(id);
      await onCloned();
    } catch {
      // best-effort — the list just won't reflect it; user can retry
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-3.5 pt-1">
      {error && (
        <div className="rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">{error}</div>
      )}
      {success && (
        <div className="rounded-xl border border-a3/25 bg-a3/10 px-3.5 py-2.5 text-sm text-a3">
          Voice cloned — switch to the Generate tab to use it.
        </div>
      )}

      <AudioRecorder value={audio} onChange={setAudio} />

      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-2">Voice name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. My voice"
          maxLength={50}
          className="w-full rounded-2xl border border-border-soft bg-surface px-4 py-3 text-[14px] outline-none placeholder:text-text-3"
        />
      </div>

      <div>
        <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-text-2">
          What the sample says <span className="normal-case text-text-3">(optional, improves quality)</span>
        </label>
        <input
          type="text"
          value={referenceText}
          onChange={(e) => setReferenceText(e.target.value)}
          placeholder="Transcript of the recording"
          maxLength={500}
          className="w-full rounded-2xl border border-border-soft bg-surface px-4 py-3 text-[14px] outline-none placeholder:text-text-3"
        />
      </div>

      {voiceModels !== null && voiceModels.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-2">
            Your cloned voices ({voiceModels.length})
          </div>
          <div className="flex flex-col gap-2">
            {voiceModels.map((vm) => (
              <div key={vm.id} className="flex items-center gap-3 rounded-2xl border border-border-soft bg-surface px-3.5 py-3">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-2">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
                    <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
                    <path d="M19 10v2a7 7 0 01-14 0v-2" />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[13px] font-medium">{vm.title}</div>
                  <div className="text-[11px] text-text-2">Ready</div>
                </div>
                <button
                  onClick={() => handleDelete(vm.id)}
                  disabled={deletingId === vm.id}
                  className="p-1.5 text-text-2 active:text-danger disabled:opacity-50"
                  aria-label="Delete voice"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="fixed bottom-16 left-0 right-0 px-4 pb-4 pt-3" style={{ background: "linear-gradient(0deg, var(--bg) 65%, transparent)" }}>
        <button
          onClick={handleClone}
          disabled={!canClone}
          className="grad-bg flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c] disabled:opacity-50"
        >
          {submitting ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#120a1c]/30 border-t-[#120a1c]" />
              Cloning…
            </>
          ) : (
            "Create clone"
          )}
        </button>
      </div>
    </div>
  );
}

function ResultView({ job, onCreateAnother }: { job: JobResponse; onCreateAnother: () => void }) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [visibility, setVisibility] = useState(job.visibility);
  const [toggling, setToggling] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!job.output?.asset_url) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    api
      .assetBlobUrl(job.output.asset_url)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setAudioUrl(url);
      })
      .catch(() => setLoadError("Couldn't load the audio."));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [job.output?.asset_url]);

  async function togglePublic() {
    setToggling(true);
    try {
      const updated = await api.setVisibility(job.id, visibility === "public" ? "private" : "public");
      setVisibility(updated.visibility);
    } catch {
      // best-effort — leave visibility as-is on failure
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="pt-2">
      <div className="flex flex-col items-center pb-1 pt-2.5 text-center">
        <div className="mb-3.5 flex h-14 w-14 items-center justify-center rounded-full border border-a3/35 bg-a3/10 text-a3">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <polyline points="20,6 9,17 4,12" />
          </svg>
        </div>
        <div className="font-display font-bold text-[19px]">Your speech is ready</div>
        <div className="mt-1 text-[12.5px] text-text-2">{job.actual_cost} credits charged</div>
      </div>

      <div className="mt-5 rounded-[20px] border border-border-soft bg-surface p-4.5">
        {loadError && <p className="text-sm text-danger">{loadError}</p>}
        {!loadError && (
          <audio controls src={audioUrl ?? undefined} className="w-full">
            Your browser doesn&apos;t support audio playback.
          </audio>
        )}
      </div>

      <button
        onClick={togglePublic}
        disabled={toggling}
        className="mt-3.5 flex w-full items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
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
        <div className={`h-[26px] w-11 flex-shrink-0 rounded-full transition-colors ${visibility === "public" ? "grad-bg" : "bg-surface-2 border border-border"}`}>
          <div
            className="h-[21px] w-[21px] rounded-full bg-white shadow transition-transform"
            style={{ transform: visibility === "public" ? "translate(20px, 2.5px)" : "translate(2.5px, 2.5px)" }}
          />
        </div>
      </button>

      <div className="pb-24 pt-6">
        <button onClick={onCreateAnother} className="grad-bg w-full rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c]">
          Create another
        </button>
        <Link href="/app" className="mt-3 block text-center text-[13px] text-text-2">
          Back to Explore
        </Link>
      </div>
    </div>
  );
}
