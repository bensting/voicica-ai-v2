"use client";

import Image from "next/image";
import Link from "next/link";
import { logCtaClick } from "@/components/Analytics";
import { PLAY_STORE_URL } from "@/lib/constants";

/** `isAndroid` is decided server-side (`lib/device.ts`, from the request's
 * own `User-Agent` header) and passed down — so the *first* render already
 * has the right primary action, never a client-side sniff-then-swap flash.
 * Both actions are always present either way (ADR 0021: this page's only
 * two exits), just reordered/resized by which one the visitor is more
 * likely to actually want. */
export function ConversionCtas({ isAndroid }: { isAndroid: boolean }) {
  const playBadge = (
    <a
      href={PLAY_STORE_URL}
      onClick={() => logCtaClick("download_android")}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-block"
    >
      <Image src="/brand/google-play-badge.svg" alt="Get it on Google Play" width={162} height={48} />
    </a>
  );

  const webButton = (
    <Link
      href="/login"
      onClick={() => logCtaClick("get_started_web")}
      className="grad-bg inline-block rounded-2xl px-8 py-4 text-base font-semibold text-[#120a1c]"
    >
      Get started free
    </Link>
  );

  if (isAndroid) {
    return (
      <div className="flex flex-col items-center gap-4">
        {playBadge}
        <Link
          href="/login"
          onClick={() => logCtaClick("get_started_web")}
          className="text-sm font-medium text-text-2 underline underline-offset-4 hover:text-text"
        >
          or continue on the web →
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4">
      {webButton}
      <div className="flex flex-col items-center gap-2">
        <span className="text-xs text-text-3">Also on Android</span>
        {playBadge}
      </div>
    </div>
  );
}
