"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useState } from "react";

interface ToastItem {
  id: number;
  message: string;
  tone: "success" | "error" | "info";
  href?: string;
}

interface ToastContextValue {
  show: (message: string, options?: { tone?: ToastItem["tone"]; href?: string }) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

/** A minimal, app-wide toast — no library, this is the first place one was
 * needed (ADR 0018's "submit gives immediate feedback, doesn't block"
 * flow: a brief confirmation on submit, then a real one when the job
 * actually finishes). Lives above `(app)`'s page content in the layout so
 * a toast fired from one page survives navigating to another before it
 * auto-dismisses. */
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const router = useRouter();

  const show = useCallback<ToastContextValue["show"]>((message, options) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, message, tone: options?.tone ?? "info", href: options?.href }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 top-0 z-[100] flex flex-col items-center gap-2 px-4 pt-[max(1rem,env(safe-area-inset-top))]">
        {toasts.map((t) => (
          <button
            key={t.id}
            onClick={() => {
              if (t.href) router.push(t.href);
              setToasts((prev) => prev.filter((x) => x.id !== t.id));
            }}
            className={`pointer-events-auto max-w-sm rounded-2xl border px-4 py-3 text-left text-[13px] font-medium shadow-lg backdrop-blur-xl transition-transform active:scale-[0.98] ${
              t.tone === "error"
                ? "border-danger/30 bg-danger/15 text-danger"
                : t.tone === "success"
                  ? "border-a3/30 bg-a3/15 text-text-1"
                  : "border-border-soft bg-surface/95 text-text-1"
            }`}
          >
            {t.message}
          </button>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
