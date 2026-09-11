"use client";

import { useEffect } from "react";

/** The top-left drawer — placeholder only for now (explicit request: just
 * the icon + an empty panel first). Eventually holds the language switcher
 * (writes lib/locale.ts's cookie, ADR 0013) plus account-level settings;
 * the trigger icon in Home's header is real, the contents aren't yet. */
export function SettingsDrawer({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
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
      <div className="fixed left-0 top-0 bottom-0 z-50 w-[78%] max-w-xs bg-sheet border-r border-border-soft animate-slide-in-left p-5">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="font-display font-bold text-lg">Settings</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="flex h-8 w-8 items-center justify-center rounded-full text-text-2 active:bg-surface-2"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <p className="text-sm text-text-2">Language and account settings are coming soon.</p>
      </div>
    </>
  );
}
