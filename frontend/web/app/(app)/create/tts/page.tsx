"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type JobResponse } from "@/lib/api";

const MAX_CHARS = 500;

export default function CreateTtsPage() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<JobResponse | null>(null);

  async function handleGenerate() {
    if (!text.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await api.submitTts(text.trim());
      setJob(result);
      if (result.status === "failed") {
        setError(result.error ?? "Generation failed.");
      }
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
      </div>

      <div className="fixed bottom-16 left-0 right-0 px-4 pb-4 pt-3" style={{ background: "linear-gradient(0deg, var(--bg) 65%, transparent)" }}>
        <button
          onClick={handleGenerate}
          disabled={submitting || !text.trim()}
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
      const next = visibility === "public" ? "private" : "public";
      const updated = await api.setVisibility(job.id, next);
      setVisibility(updated.visibility);
    } catch {
      // best-effort — leave visibility as-is on failure
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col px-4">
      <header className="flex items-center justify-between pb-3.5 pt-[18px]">
        <Link href="/" className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-border-soft bg-surface">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text)" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </Link>
        <span className="font-display font-bold text-[15px]">Result</span>
        <div className="w-[34px]" />
      </header>

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
          <audio controls src={audioUrl ?? undefined} className="w-full" data-loading={!audioUrl}>
            Your browser doesn&apos;t support audio playback.
          </audio>
        )}
      </div>

      <div className="mt-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5">
        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-3">Script</div>
        <div className="text-[13px] leading-relaxed text-text-2">&quot;{job.input.text}&quot;</div>
      </div>

      <button
        onClick={togglePublic}
        disabled={toggling}
        className="mt-3.5 flex items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
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

      <div className="mt-auto pb-24 pt-6">
        <button
          onClick={onCreateAnother}
          className="grad-bg w-full rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c]"
        >
          Create another
        </button>
      </div>
    </div>
  );
}
