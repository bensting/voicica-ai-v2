"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type MenuItem } from "@/lib/api";
import { MenuIcon } from "./icons";

/** The "+" button's sheet — every item, in every language, comes from the
 * backend (GET /config/menu, docs: services/menu.py); this component has
 * zero knowledge of which capabilities exist, just how to lay one out. */
export function CreateSheet({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const [items, setItems] = useState<MenuItem[] | null>(null);

  useEffect(() => {
    if (isOpen && items === null) {
      api.getMenu().then(setItems).catch(() => setItems([]));
    }
  }, [isOpen, items]);

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
      <div
        className="fixed left-0 right-0 z-50 rounded-t-3xl bg-sheet border-t border-border-soft animate-slide-up"
        style={{ bottom: "calc(64px + env(safe-area-inset-bottom, 0px))" }}
      >
        <div className="mx-auto max-w-md p-3 space-y-1.5">
          {items === null && (
            <div className="flex justify-center py-8">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
            </div>
          )}
          {items?.length === 0 && (
            <p className="py-8 text-center text-sm text-text-2">Nothing available yet.</p>
          )}
          {items?.map((item) => (
            <Link
              key={item.id}
              href={item.route}
              onClick={onClose}
              className="flex items-center gap-3 rounded-xl bg-surface px-3 py-2.5 active:bg-surface-2"
            >
              <div className="text-text-2">
                <MenuIcon name={item.icon} width={20} height={20} />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="truncate text-sm font-medium text-text">{item.label}</h3>
                <p className="truncate text-xs text-text-2">{item.description}</p>
              </div>
              {item.badge && (
                <span className="shrink-0 rounded-full bg-a5/15 px-1.5 py-0.5 text-[10px] font-semibold text-a5">
                  {item.badge}
                </span>
              )}
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" className="shrink-0">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </Link>
          ))}
        </div>
        <div className="pb-3" />
      </div>
    </>
  );
}
