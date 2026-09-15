"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { APP_CONTENT_WIDTH } from "@/lib/layout";
import { useJobEvents } from "@/lib/job-events";
import { CreateSheet } from "./CreateSheet";

export function BottomNav() {
  const pathname = usePathname();
  const isHome = pathname === "/app";
  const isMe = pathname === "/app/me";
  const [sheetOpen, setSheetOpen] = useState(false);
  const { pendingCount } = useJobEvents();

  return (
    <>
      <nav
        className="fixed bottom-0 left-0 right-0 z-40 bg-bg/85 backdrop-blur-xl border-t border-border-soft"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        <div className={`mx-auto flex h-16 items-center ${APP_CONTENT_WIDTH}`}>
          <Link
            href="/app"
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
            <button
              onClick={() => setSheetOpen((v) => !v)}
              className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-2 border border-border active:scale-95 transition-transform"
            >
              <svg
                width="19"
                height="19"
                viewBox="0 0 24 24"
                fill="none"
                stroke="var(--text-2)"
                strokeWidth="2"
                className={`transition-transform ${sheetOpen ? "rotate-45" : ""}`}
              >
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
            </button>
          </div>

          <Link
            href="/app/me"
            className="relative flex flex-1 h-full flex-col items-center justify-center gap-0.5"
          >
            <span className="relative">
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
              {/* ADR 0018: how many of the user's own jobs are still
                  pending/processing — the "check on progress" cue that
                  doesn't require having caught the toast when it happened. */}
              {pendingCount > 0 && (
                <span className="absolute -right-2 -top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-a3 px-1 text-[9px] font-bold text-white">
                  {pendingCount > 9 ? "9+" : pendingCount}
                </span>
              )}
            </span>
            <span className={`text-[11px] ${isMe ? "text-text font-medium" : "text-text-3"}`}>
              Me
            </span>
          </Link>
        </div>
      </nav>

      <CreateSheet isOpen={sheetOpen} onClose={() => setSheetOpen(false)} />
    </>
  );
}
