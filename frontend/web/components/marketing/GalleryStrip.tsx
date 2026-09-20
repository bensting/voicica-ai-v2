"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type GalleryItem } from "@/lib/api";
import { en as content } from "@/content/marketing/en";

/** A real, unauthenticated strip of `GET /gallery` (ADR 0010) on the
 * homepage — genuine captions/timestamps, not mockup content. Text-only for
 * now (ADR 0019): a public item's `output.asset_url` is a direct public R2
 * URL since ADR 0027, so thumbnails/playback here are now a pure design
 * choice rather than an auth-boundary problem — just not built yet. */
export function GalleryStrip() {
  const [items, setItems] = useState<GalleryItem[] | null>(null);

  useEffect(() => {
    api.getGallery().then((page) => setItems(page.items.slice(0, 6))).catch(() => setItems([]));
  }, []);

  return (
    <section className="px-5 py-16 sm:px-8 md:py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 text-center">
          <h2 className="font-display text-2xl font-bold md:text-3xl">{content.home.galleryStrip.title}</h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-text-2">{content.home.galleryStrip.subtitle}</p>
        </div>

        {items && items.length === 0 && (
          <p className="text-center text-sm text-text-2">{content.home.galleryStrip.emptyText}</p>
        )}

        {items && items.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item) => (
              <GalleryCard key={item.id} item={item} />
            ))}
          </div>
        )}

        <div className="mt-8 text-center">
          <Link href="/login" className="text-sm font-semibold text-a3">
            {content.home.galleryStrip.ctaText} →
          </Link>
        </div>
      </div>
    </section>
  );
}

function kindFor(capability: string): "audio" | "image" | "video" {
  if (capability === "tts") return "audio";
  if (capability === "image-to-video") return "video";
  return "image";
}

function captionFor(item: GalleryItem): string {
  return item.input.text ?? (item.input.inputs?.prompt as string | undefined) ?? "Untitled";
}

function GalleryCard({ item }: { item: GalleryItem }) {
  const kind = kindFor(item.capability);
  return (
    <div className="flex items-start gap-3 rounded-2xl border border-border-soft bg-surface p-4">
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-a3/15 text-a3">
        <KindIcon kind={kind} />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{captionFor(item)}</p>
        <p className="mt-0.5 text-xs text-text-3">
          {item.provider} · {new Date(item.created_at).toLocaleDateString()}
        </p>
      </div>
    </div>
  );
}

function KindIcon({ kind }: { kind: "audio" | "image" | "video" }) {
  if (kind === "audio") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
        <path d="M8 5v14l11-7z" />
      </svg>
    );
  }
  if (kind === "video") {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6">
        <rect x="2" y="5" width="14" height="14" rx="2.5" />
        <path d="M16 9.5l5-3v11l-5-3z" />
      </svg>
    );
  }
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="18" height="18" rx="2.5" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="M21 15l-5-5L5 21" />
    </svg>
  );
}
