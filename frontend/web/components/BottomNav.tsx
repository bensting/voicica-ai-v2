"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function BottomNav() {
  const pathname = usePathname();
  const isHome = pathname === "/";
  const isMe = pathname === "/me";

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 bg-bg/85 backdrop-blur-xl border-t border-border-soft"
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
    >
      <div className="mx-auto flex h-16 max-w-md items-center">
        <Link
          href="/"
          className="flex flex-1 h-full flex-col items-center justify-center gap-0.5"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill={isHome ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth="2"
            className={isHome ? "text-text" : "text-text-3"}
          >
            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
            {!isHome && <path d="M9 22V12h6v10" />}
          </svg>
          <span className={`text-[11px] ${isHome ? "text-text font-medium" : "text-text-3"}`}>
            Explore
          </span>
        </Link>

        <div className="flex flex-1 h-full items-center justify-center">
          <Link
            href="/create/tts"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-2 border border-border active:scale-95 transition-transform"
          >
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="var(--text-2)" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </Link>
        </div>

        <Link
          href="/me"
          className="flex flex-1 h-full flex-col items-center justify-center gap-0.5"
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill={isMe ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth="2"
            className={isMe ? "text-text" : "text-text-3"}
          >
            <circle cx="12" cy="8" r="4" />
            <path d="M20 21a8 8 0 10-16 0" />
          </svg>
          <span className={`text-[11px] ${isMe ? "text-text font-medium" : "text-text-3"}`}>
            Me
          </span>
        </Link>
      </div>
    </nav>
  );
}
