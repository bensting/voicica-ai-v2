"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api, type GalleryItem } from "@/lib/api";
import { CreditsPill } from "@/components/CreditsPill";
import { SettingsDrawer } from "@/components/SettingsDrawer";

/** Home = "Explore" (the bottom nav's label for this tab) — the public
 * gallery (ADR 0010), not the signed-in user's own history (that's
 * `/app/me`). Two different things; showing "your creations" here was a
 * mix-up caught in review — nothing in the data model changed, just which
 * feed this page reads. */
export default function HomePage() {
  const [items, setItems] = useState<GalleryItem[] | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [playingId, setPlayingId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const blobUrlsRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    api.getGallery().then((page) => setItems(page.items)).catch(() => setItems([]));
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
        <div className="flex items-baseline justify-between">
          <h2 className="font-display font-bold text-[15px]">Explore</h2>
          <Link href="/app/create/tts" className="text-xs font-semibold text-a3">
            + New
          </Link>
        </div>

        {items === null && (
          <div className="mt-4 flex justify-center py-10">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}

        {items?.length === 0 && (
          <div className="mt-4 flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-12 text-center">
            <p className="text-sm text-text-2 max-w-[220px]">
              Nothing shared yet — be the first to publish a creation here.
            </p>
            <Link
              href="/app/create/tts"
              className="grad-bg rounded-xl px-4 py-2 text-xs font-semibold text-[#120a1c]"
            >
              Generate speech
            </Link>
          </div>
        )}

        <div className="mt-3 flex flex-col gap-2">
          {items?.map((item) => (
            <GalleryRow key={item.id} item={item} playing={playingId === item.id} onToggle={() => togglePlay(item)} />
          ))}
        </div>
      </section>
    </div>
  );
}

function GalleryRow({
  item,
  playing,
  onToggle,
}: {
  item: GalleryItem;
  playing: boolean;
  onToggle: () => void;
}) {
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
        <div className="truncate text-[13px] font-medium">{item.input.text}</div>
        <div className="mt-0.5 text-[11px] text-text-2">
          {item.provider} · {new Date(item.created_at).toLocaleString()}
        </div>
      </div>
    </div>
  );
}
