"use client";

import { useEffect, useRef, useState } from "react";
import { api, type JobResponse, type MeResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useJobEvents } from "@/lib/job-events";

/** capability -> what a succeeded job's own asset actually is. Mirrors the
 * same small, capability-string mapping Explore's own row/grid components
 * use (ADR 0017) — not a second source of truth, just this page's inline
 * copy of it (fetching `GET /kie/categories` just to look up one field
 * isn't worth a round trip here). */
function mediaKindFor(capability: string): "audio" | "image" | "video" | "none" {
  if (capability === "tts") return "audio";
  if (capability === "voice_model_training") return "none"; // a trained voice, not a playable asset
  if (capability === "image-to-video") return "video";
  return "image"; // text-to-image, image-to-image, and any future Kie image category
}

// History's own filter tabs. "Generating" is cross-capability (every
// pending/processing job, whatever it is) rather than a fifth media kind —
// once a job leaves that state (success or failure) it moves into its own
// capability tab below, so a tab never shows the same job twice. Voice-clone
// *training* records (no playable media, `mediaKindFor` == "none") still
// belong under "Voices" here, since this list is where they live at all
// (Explore never shows them, only real audio results do).
const HISTORY_TABS = ["Generating", "Voices", "Images", "Videos"] as const;
type HistoryTab = (typeof HISTORY_TABS)[number];

function historyTabFor(capability: string): Exclude<HistoryTab, "Generating"> {
  if (capability === "tts" || capability === "voice_model_training") return "Voices";
  if (capability === "image-to-video") return "Videos";
  return "Images";
}

function isInProgress(job: JobResponse): boolean {
  return job.status === "pending" || job.status === "processing";
}

function captionFor(job: JobResponse): string {
  return (
    job.input.text ??
    (job.input.inputs?.prompt as string | undefined) ??
    job.input.title ??
    "Untitled"
  );
}

/** Home = "Explore" (ADR 0010) is the public gallery; this page is the
 * signed-in user's own full history — every job, not just public ones,
 * and the one place a result is actually viewed now (ADR 0018 moved every
 * create page off "wait here for the result inline" — submitting just
 * shows a toast and returns the form, so this list is where "did it
 * finish, and what did I get" gets answered, live). */
export default function MePage() {
  const { user, signOut } = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [jobs, setJobs] = useState<JobResponse[] | null>(null);
  // Defaults to "Generating" — this page is where a submit's result is
  // actually watched now (ADR 0018), so the tab most worth landing on is
  // whatever's still in flight, not a finished-history tab.
  const [activeTab, setActiveTab] = useState<HistoryTab>("Generating");
  const { lastEvent } = useJobEvents();

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
    api.listJobs().then(setJobs).catch(() => setJobs([]));
  }, []);

  // Live-patch just the one row an SSE event names, instead of re-fetching
  // the whole list — `GET /jobs/{id}` for one job is cheap, and gets this
  // page an up-to-date `output`/`actual_cost`/`error` for that row, which
  // the event payload itself deliberately doesn't carry (ADR 0018).
  useEffect(() => {
    if (!lastEvent) return;
    api.getJob(lastEvent.job_id).then((updated) => {
      setJobs((prev) => prev?.map((j) => (j.id === updated.id ? updated : j)) ?? prev);
    }).catch(() => {});
  }, [lastEvent]);

  function updateJob(updated: JobResponse) {
    setJobs((prev) => prev?.map((j) => (j.id === updated.id ? updated : j)) ?? prev);
  }

  const publicCount = jobs?.filter((j) => j.visibility === "public").length ?? null;
  const visibleJobs = jobs?.filter((j) =>
    activeTab === "Generating" ? isInProgress(j) : !isInProgress(j) && historyTabFor(j.capability) === activeTab,
  );

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[8%] -right-[14%] w-[60%] h-[30%] rounded-full bg-a1/15 blur-[90px]" />
      </div>

      <header className="relative flex items-center gap-3.5 px-5 pb-1.5 pt-6">
        <div className="grad-bg flex h-[54px] w-[54px] items-center justify-center rounded-full font-display text-xl font-bold text-[#120a1c]">
          {(user?.email ?? "?").charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-[17px] font-bold truncate">
            {user?.displayName ?? "Your account"}
          </div>
          <div className="mt-0.5 truncate text-xs text-text-2">{user?.email}</div>
        </div>
        <button
          onClick={() => signOut()}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[10px] border border-border-soft bg-surface text-text-2"
          title="Sign out"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
            <polyline points="16,17 21,12 16,7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </header>

      <div className="relative mx-5 mt-4 flex items-center justify-between rounded-[20px] border border-border-soft bg-surface p-4.5">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-text-3">Balance</div>
          <div className="mt-0.5 font-display text-[26px] font-bold tabular-nums">
            {me ? me.balance.toLocaleString() : "…"}
          </div>
        </div>
        <button className="grad-bg rounded-xl px-4 py-2.5 text-[13px] font-semibold text-[#120a1c]">
          Top up
        </button>
      </div>

      <div className="relative mx-5 mt-2.5 grid grid-cols-2 gap-2.5">
        <StatTile label="Creations" value={jobs?.length ?? null} />
        <StatTile label="Public" value={publicCount} />
      </div>

      <section className="relative px-5 pt-6 pb-4">
        <h2 className="mb-2 font-display text-[15px] font-bold">History</h2>

        <div className="mb-3 flex gap-5 border-b border-border-soft">
          {HISTORY_TABS.map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`-mb-px border-b-2 pb-2 text-[13.5px] font-medium transition-colors ${
                activeTab === tab ? "border-a3 text-text-1" : "border-transparent text-text-3"
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {jobs === null && (
          <div className="flex justify-center py-8">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}
        {jobs?.length === 0 && (
          <p className="py-6 text-center text-sm text-text-2">No creations yet.</p>
        )}
        {jobs && jobs.length > 0 && visibleJobs?.length === 0 && (
          <p className="py-6 text-center text-sm text-text-2">
            {activeTab === "Generating" ? "Nothing generating right now." : "Nothing here yet."}
          </p>
        )}
        <div className="flex flex-col gap-2">
          {visibleJobs?.map((job) => (
            <JobCard key={job.id} job={job} onUpdate={updateJob} />
          ))}
        </div>
      </section>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-2xl border border-border-soft bg-surface px-3 py-3 text-center">
      <div className="font-display text-lg font-bold tabular-nums">{value ?? "…"}</div>
      <div className="mt-0.5 text-[10.5px] text-text-2">{label}</div>
    </div>
  );
}

function JobCard({ job, onUpdate }: { job: JobResponse; onUpdate: (job: JobResponse) => void }) {
  const [toggling, setToggling] = useState(false);
  const caption = captionFor(job);
  const kind = mediaKindFor(job.capability);
  const assetUrl = job.output?.asset_url;
  const hasAsset = job.status === "succeeded" && kind !== "none" && Boolean(assetUrl);

  async function togglePublic() {
    setToggling(true);
    try {
      const updated = await api.setVisibility(job.id, job.visibility === "public" ? "private" : "public");
      onUpdate(updated);
    } catch {
      // best-effort — leave visibility as-is on failure
    } finally {
      setToggling(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-border-soft bg-surface">
      <div className="flex items-center gap-3 p-3">
        {hasAsset && (kind === "image" || kind === "video") ? (
          <ThumbnailGlyph assetUrl={assetUrl as string} kind={kind} caption={caption} />
        ) : (
          <StatusGlyph job={job} kind={kind} />
        )}
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium">{caption}</div>
          <div className="mt-0.5 text-[11px] text-text-2">
            {job.provider} · {new Date(job.created_at).toLocaleDateString()}
            {job.status === "failed" && job.error && (
              <span className="text-danger"> · {job.error}</span>
            )}
          </div>
        </div>
        {job.status === "succeeded" && kind !== "none" && (
          <button
            onClick={togglePublic}
            disabled={toggling}
            className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold disabled:opacity-50 ${
              job.visibility === "public" ? "text-success bg-success/10" : "text-text-2 bg-white/5"
            }`}
          >
            {job.visibility === "public" ? "Public" : "Private"}
          </button>
        )}
      </div>

      {/* Voices stay directly playable inline — nothing to preview visually,
          so the sheet Image/Video get would just be an extra tap. */}
      {hasAsset && kind === "audio" && <InlineAudio assetUrl={assetUrl as string} />}
    </div>
  );
}

/** The small icon on the left of a job card: a spinner while pending/
 * processing, a failure glyph, or a kind-appropriate icon once succeeded
 * (voice-clone training has no playable media, so it keeps an icon rather
 * than the media strip below). */
function StatusGlyph({
  job,
  kind,
}: {
  job: JobResponse;
  kind: "audio" | "image" | "video" | "none";
}) {
  const base = "flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full";

  if (job.status === "pending" || job.status === "processing") {
    return (
      <div className={`${base} bg-surface-2`}>
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
      </div>
    );
  }
  if (job.status === "failed") {
    return (
      <div className={`${base} bg-danger/10 text-danger`}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </div>
    );
  }
  // succeeded
  return (
    <div className={`${base} bg-a3/15 text-a3`}>
      {kind === "audio" && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
          <path d="M8 5v14l11-7z" />
        </svg>
      )}
      {kind === "image" && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="3" y="3" width="18" height="18" rx="2.5" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <path d="M21 15l-5-5L5 21" />
        </svg>
      )}
      {kind === "video" && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
          <rect x="2" y="5" width="14" height="14" rx="2.5" />
          <path d="M16 9.5l5-3v11l-5-3z" />
        </svg>
      )}
      {kind === "none" && (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <polyline points="20,6 9,17 4,12" />
        </svg>
      )}
    </div>
  );
}

/** Voices keep direct inline playback below the row — nothing to preview
 * visually, so the bottom-sheet treatment Image/Video get would just be an
 * extra tap for no benefit (the user's own call: "Voices没有必要可以直接
 * 播放"). Lazy via the same `IntersectionObserver` pattern used everywhere
 * else in this list, fetched through the same auth'd `assetBlobUrl()`. */
function InlineAudio({ assetUrl }: { assetUrl: string }) {
  const [inView, setInView] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!inView) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    api.assetBlobUrl(assetUrl).then((blobUrl) => {
      if (cancelled) {
        URL.revokeObjectURL(blobUrl);
        return;
      }
      objectUrl = blobUrl;
      setUrl(blobUrl);
    }).catch(() => setLoadError("Couldn't load the audio."));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [inView, assetUrl]);

  return (
    <div ref={containerRef} className="border-t border-border-soft p-3">
      {loadError && <p className="text-[12px] text-danger">{loadError}</p>}
      {!loadError && !url && (
        <div className="flex justify-center py-1">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
        </div>
      )}
      {!loadError && url && (
        <audio controls src={url} className="w-full">
          Your browser doesn&apos;t support audio playback.
        </audio>
      )}
    </div>
  );
}

/** Image/Video row glyph, replacing what used to be a full inline
 * expansion of every result (rejected — "我建议是每条记录都有个查看图标
 * 然后统一从底部弹出"). A small lazy-loaded thumbnail doubles as the tap
 * target for the "view" icon overlaid on it; tapping opens the same
 * asset, full-size, in `MediaViewSheet`. Same `IntersectionObserver` +
 * `assetBlobUrl()` lazy-load this list already used for full media, just
 * fetched once and reused for both the thumbnail and the sheet. */
function ThumbnailGlyph({
  assetUrl,
  kind,
  caption,
}: {
  assetUrl: string;
  kind: "image" | "video";
  caption: string;
}) {
  const [inView, setInView] = useState(false);
  const [url, setUrl] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const containerRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { rootMargin: "400px 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!inView) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    api.assetBlobUrl(assetUrl).then((blobUrl) => {
      if (cancelled) {
        URL.revokeObjectURL(blobUrl);
        return;
      }
      objectUrl = blobUrl;
      setUrl(blobUrl);
    }).catch(() => {
      // best-effort thumbnail — the sheet's own load (re-fetch on open) can
      // still surface an error if it matters at that point.
    });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [inView, assetUrl]);

  return (
    <>
      <button
        ref={containerRef}
        onClick={() => setSheetOpen(true)}
        className="relative h-11 w-11 flex-shrink-0 overflow-hidden rounded-xl bg-surface-2"
      >
        {url && kind === "image" && (
          // eslint-disable-next-line @next/next/no-img-element -- a fetched, auth-gated Blob URL, not a static/remote asset next/image can optimize
          <img src={url} alt={caption} className="h-full w-full object-cover" />
        )}
        {url && kind === "video" && (
          <video src={url} muted playsInline preload="metadata" className="h-full w-full object-cover" />
        )}
        {!url && (
          <div className="flex h-full w-full items-center justify-center">
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/25 text-white">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </div>
      </button>

      <MediaViewSheet
        isOpen={sheetOpen}
        onClose={() => setSheetOpen(false)}
        url={url}
        kind={kind}
        caption={caption}
      />
    </>
  );
}

/** The unified "view" sheet for Image/Video results — same bottom-sheet
 * visual language `CreateSheet` already established (rounded-t-3xl sheet +
 * blurred backdrop), reused rather than inventing a second sheet pattern.
 * Unlike `CreateSheet` this one covers the bottom nav — it's a focused
 * viewer, not another place to navigate from. Download uses a plain
 * `<a download>` on the already-fetched blob URL (no second request). */
function MediaViewSheet({
  isOpen,
  onClose,
  url,
  kind,
  caption,
}: {
  isOpen: boolean;
  onClose: () => void;
  url: string | null;
  kind: "image" | "video";
  caption: string;
}) {
  useEffect(() => {
    document.body.style.overflow = isOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-3xl border-t border-border-soft bg-sheet animate-slide-up">
        <div className="mx-auto max-w-md p-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="min-w-0 flex-1 truncate text-sm font-medium">{caption}</h3>
            <button
              onClick={onClose}
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-2"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {!url && (
            <div className="flex justify-center py-10">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
            </div>
          )}
          {url && kind === "image" && (
            // eslint-disable-next-line @next/next/no-img-element -- a fetched, auth-gated Blob URL, not a static/remote asset next/image can optimize
            <img src={url} alt={caption} className="w-full rounded-xl" />
          )}
          {url && kind === "video" && (
            <video src={url} controls playsInline className="w-full rounded-xl" />
          )}
          {url && (
            <a
              href={url}
              download
              className="mt-3 flex items-center justify-center gap-2 rounded-xl bg-surface-2 py-2.5 text-[13px] font-semibold text-text"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                <polyline points="7,10 12,15 17,10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              Download
            </a>
          )}
        </div>
        <div style={{ paddingBottom: "calc(12px + env(safe-area-inset-bottom, 0px))" }} />
      </div>
    </>
  );
}
