"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type GalleryItem } from "@/lib/api";
import { CreditsPill } from "@/components/CreditsPill";
import { SettingsDrawer } from "@/components/SettingsDrawer";

// Explore's three tabs — one per `output_type` (ADR 0017's own audio/
// image/video vocabulary, reused rather than inventing a second
// classification). Each tab's empty-state CTA points at a real category
// for that type, not a single hardcoded "Generate speech" route that only
// made sense back when TTS was the only capability.
const TABS = [
  { key: "audio", label: "Voices", createRoute: "/app/create/tts", createLabel: "Generate speech" },
  { key: "image", label: "Images", createRoute: "/app/create/kie/text-to-image", createLabel: "Generate an image" },
  { key: "video", label: "Videos", createRoute: "/app/create/kie/image-to-video", createLabel: "Generate a video" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

/** Home = "Explore" (the bottom nav's label for this tab) — the public
 * gallery (ADR 0010), not the signed-in user's own history (that's
 * `/app/me`). Two different things; showing "your creations" here was a
 * mix-up caught in review — nothing in the data model changed, just which
 * feed this page reads. */
export default function HomePage() {
  const [activeTab, setActiveTab] = useState<TabKey>("audio");
  // Keyed by tab, undefined = not fetched yet, [] = fetched and empty — a
  // tab switched back to doesn't refetch (ADR 0010's gallery has no
  // real-time push, so a stale-for-this-session list is an acceptable
  // trade for not re-hitting the DB every tab click).
  const [itemsByTab, setItemsByTab] = useState<Partial<Record<TabKey, GalleryItem[]>>>({});
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlsRef = useRef<Map<string, string>>(new Map());

  const items = itemsByTab[activeTab];

  useEffect(() => {
    if (itemsByTab[activeTab] !== undefined) return;
    api
      .getGallery({ outputType: activeTab })
      .then((page) => setItemsByTab((prev) => ({ ...prev, [activeTab]: page.items })))
      .catch(() => setItemsByTab((prev) => ({ ...prev, [activeTab]: [] })));
  }, [activeTab, itemsByTab]);

  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;
    const onEnded = () => setPlayingId(null);
    audio.addEventListener("ended", onEnded);
    const blobUrls = blobUrlsRef.current;
    return () => {
      audio.removeEventListener("ended", onEnded);
      audio.pause();
      blobUrls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  async function togglePlay(item: GalleryItem) {
    // Only a TTS-shaped item (`input.text`) is playable audio — a Kie item
    // (`input.inputs`, ADR 0015) renders a static thumbnail row instead
    // (GalleryRow below), so this never actually gets called for one, but
    // guarding here too keeps this function correct on its own.
    if (item.input.inputs) return;
    const audio = audioRef.current;
    if (!audio || !item.output?.asset_url) return;

    if (playingId === item.id) {
      audio.pause();
      setPlayingId(null);
      return;
    }

    let url = blobUrlsRef.current.get(item.id);
    if (!url) {
      try {
        url = await api.assetBlobUrl(item.output.asset_url);
        blobUrlsRef.current.set(item.id, url);
      } catch {
        return;
      }
    }
    audio.src = url;
    audio.play().catch((e: DOMException) => {
      // Switching tracks quickly aborts the previous play() promise
      // (AbortError, "interrupted by a new load request") — expected, not a
      // real failure, and by the time it rejects `playingId` may already
      // have moved on to whatever was clicked next. Only clear it if it's
      // still pointing at *this* item, so a superseded rejection can't
      // clobber a newer selection.
      if (e.name !== "AbortError") console.error("Playback failed:", e);
      setPlayingId((current) => (current === item.id ? null : current));
    });
    setPlayingId(item.id);
  }

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[8%] -left-[10%] w-[60%] h-[30%] rounded-full bg-a1/15 blur-[90px]" />
      </div>

      <header className="relative flex items-center justify-between px-5 pt-6 pb-2">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setDrawerOpen(true)}
            aria-label="Open menu"
            className="flex h-8 w-8 items-center justify-center rounded-full text-text-2 active:bg-surface-2"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="4" y1="7" x2="20" y2="7" />
              <line x1="4" y1="12" x2="20" y2="12" />
              <line x1="4" y1="17" x2="14" y2="17" />
            </svg>
          </button>
          <div className="flex items-center gap-2.5">
            <Image src="/brand/mark.webp" alt="" width={30} height={30} priority />
            <span className="font-display font-bold text-[17px] tracking-tight">Voicica</span>
          </div>
        </div>
        <CreditsPill />
      </header>

      <SettingsDrawer isOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />

      <section className="relative px-5 pt-6">
        <h2 className="font-display font-bold text-[15px]">Explore</h2>

        <div className="mt-3 flex gap-5 border-b border-border-soft">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`-mb-px border-b-2 pb-2 text-[13.5px] font-medium transition-colors ${
                activeTab === tab.key
                  ? "border-a3 text-text-1"
                  : "border-transparent text-text-3"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {items === undefined && (
          <div className="mt-4 flex justify-center py-10">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}

        {items?.length === 0 && (
          <div className="mt-4 flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-12 text-center">
            <p className="text-sm text-text-2 max-w-[220px]">
              Nothing shared here yet — be the first to publish one.
            </p>
            <Link
              href={TABS.find((t) => t.key === activeTab)!.createRoute}
              className="grad-bg rounded-xl px-4 py-2 text-xs font-semibold text-[#120a1c]"
            >
              {TABS.find((t) => t.key === activeTab)!.createLabel}
            </Link>
          </div>
        )}

        {activeTab === "audio" ? (
          <div className="mt-3 flex flex-col gap-2">
            {items?.map((item) => (
              <VoiceRow key={item.id} item={item} playing={playingId === item.id} onToggle={() => togglePlay(item)} />
            ))}
          </div>
        ) : (
          // Images/Videos are visual content — a text row with a generic
          // icon (the previous, capability-blind version of this page)
          // threw away the one thing worth browsing for. A 2-column grid of
          // real thumbnails, caption overlaid on a bottom scrim, matches
          // the prior project's own Image tab (asked for directly) rather
          // than reinventing a gallery layout from scratch.
          // More columns as the shell itself gets wider (`APP_CONTENT_WIDTH`)
          // — the actual point of a wider desktop layout, not just 2 huge
          // thumbnails where 2 small ones used to be.
          <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-3 lg:grid-cols-4">
            {items?.map((item) => (
              <MediaCard key={item.id} item={item} isVideo={activeTab === "video"} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function VoiceRow({
  item,
  playing,
  onToggle,
}: {
  item: GalleryItem;
  playing: boolean;
  onToggle: () => void;
}) {
  const caption = item.input.text ?? "Untitled";

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border-soft bg-surface p-3">
      <button
        onClick={onToggle}
        aria-label={playing ? "Pause" : "Play"}
        className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-surface-2 text-a3 active:bg-border-soft"
      >
        {playing ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <rect x="6" y="4" width="4" height="16" />
            <rect x="14" y="4" width="4" height="16" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
        )}
      </button>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium">{caption}</div>
        <div className="mt-0.5 text-[11px] text-text-2">
          {item.provider} · {new Date(item.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}

/** One grid cell for the Images/Videos tabs. Fetches its own blob URL
 * (same auth'd `assetBlobUrl` helper the audio row already used) rather
 * than the parent pre-fetching every item up front — simpler state, and
 * fine at today's content volume; revisit with lazy/viewport-based
 * fetching if a real feed ever grows past a screen or two. */
function MediaCard({ item, isVideo }: { item: GalleryItem; isVideo: boolean }) {
  const [url, setUrl] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const caption = (item.input.inputs?.prompt as string | undefined) ?? "Untitled";

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    if (item.output?.asset_url) {
      api.assetBlobUrl(item.output.asset_url).then((blobUrl) => {
        if (cancelled) {
          URL.revokeObjectURL(blobUrl);
          return;
        }
        objectUrl = blobUrl;
        setUrl(blobUrl);
      }).catch(() => {});
    }
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [item.output?.asset_url]);

  function toggleVideo() {
    const video = videoRef.current;
    if (!video) return;
    if (playing) {
      video.pause();
    } else {
      video.play().catch(() => {});
    }
    setPlaying(!playing);
  }

  return (
    <div
      onClick={isVideo ? toggleVideo : undefined}
      className="relative aspect-[4/5] overflow-hidden rounded-2xl bg-surface"
    >
      {url === null && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
        </div>
      )}
      {url && (isVideo ? (
        <video
          ref={videoRef}
          src={url}
          muted
          playsInline
          loop
          onEnded={() => setPlaying(false)}
          className="h-full w-full object-cover"
        />
      ) : (
        // a blob: URL can't go through next/image's remote optimizer.
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={caption} className="h-full w-full object-cover" />
      ))}
      {isVideo && url && !playing && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-black/50 text-white">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          </div>
        </div>
      )}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent px-2.5 pb-2 pt-6">
        <p className="line-clamp-2 text-[12px] font-medium text-white">{caption}</p>
      </div>
    </div>
  );
}
