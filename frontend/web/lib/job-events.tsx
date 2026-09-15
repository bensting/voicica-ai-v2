"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { API_BASE, api } from "@/lib/api";
import { useToast } from "@/components/Toast";

/** Matches `services/jobs.py publish_job_event()`'s payload exactly —
 * intentionally minimal (no caption/thumbnail), enough to toast and to
 * tell a list of jobs which one to re-fetch. */
export interface JobEvent {
  job_id: string;
  status: "succeeded" | "failed";
  capability: string;
  // Client-added, not part of the wire payload — guarantees a fresh object
  // identity per event even if the same job_id somehow arrives twice, so a
  // `useEffect` keyed on `lastEvent` always re-fires.
  receivedAt: number;
}

interface JobEventsContextValue {
  /** How many of the signed-in user's own jobs are still pending/processing
   * — drives `BottomNav`'s badge. Seeded from a real `GET /jobs` count on
   * mount, then kept in sync by `registerPendingJob`/incoming events rather
   * than re-fetched on every change. */
  pendingCount: number;
  /** Call right after a create page's submit succeeds (ADR 0018 — the
   * whole point is the form doesn't block waiting for this, so the badge
   * needs telling directly, not derived from a response that already came
   * back `pending`). */
  registerPendingJob: () => void;
  /** The most recent job-completion event, or `null` before the first one
   * this session. A page showing a list of the user's own jobs (`/app/me`)
   * can `useEffect` on this to patch just that one row instead of
   * re-fetching the whole list. */
  lastEvent: JobEvent | null;
}

const JobEventsContext = createContext<JobEventsContextValue | null>(null);

// capability -> a short, human label for the toast text. Falls back to the
// raw capability string for anything not listed (a new Kie category, say)
// rather than a blank/awkward message.
const CAPABILITY_LABELS: Record<string, string> = {
  tts: "speech",
  voice_model_training: "voice clone",
  "text-to-image": "image",
  "image-to-image": "image",
  "image-to-video": "video",
};

export function JobEventsProvider({ children }: { children: React.ReactNode }) {
  const [pendingCount, setPendingCount] = useState(0);
  const [lastEvent, setLastEvent] = useState<JobEvent | null>(null);
  const { show } = useToast();
  const seededRef = useRef(false);

  const registerPendingJob = useCallback(() => setPendingCount((n) => n + 1), []);

  // Seed the initial count once, from whichever moment auth is ready —
  // not done inside the SSE effect below, since that effect's job is
  // reconnecting the stream, not re-counting from scratch every time.
  useEffect(() => {
    return onAuthStateChanged(auth, (user) => {
      if (!user || seededRef.current) return;
      seededRef.current = true;
      api.listJobs().then((jobs) => {
        const count = jobs.filter((j) => j.status === "pending" || j.status === "processing").length;
        setPendingCount(count);
      }).catch(() => {});
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    let es: EventSource | null = null;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    async function connect() {
      if (cancelled) return;
      const user = auth.currentUser;
      if (!user) {
        // Not signed in yet — retried on the same short timer rather than
        // wiring a second auth-state listener; simpler, and this only
        // matters for the few hundred ms around initial app load.
        retryTimer = setTimeout(connect, 1000);
        return;
      }
      const token = await user.getIdToken();
      if (cancelled) return;
      es = new EventSource(`${API_BASE}/events?token=${encodeURIComponent(token)}`);
      es.onmessage = (e) => {
        if (!e.data || e.data.startsWith(":")) return; // keep-alive comment lines never reach onmessage anyway
        try {
          const parsed = JSON.parse(e.data) as Omit<JobEvent, "receivedAt">;
          setLastEvent({ ...parsed, receivedAt: Date.now() });
          setPendingCount((n) => Math.max(0, n - 1));
          const label = CAPABILITY_LABELS[parsed.capability] ?? parsed.capability;
          if (parsed.status === "succeeded") {
            show(`Your ${label} is ready`, { tone: "success", href: "/app/me" });
          } else {
            show(`Your ${label} failed to generate`, { tone: "error", href: "/app/me" });
          }
        } catch {
          // malformed payload — never crash the whole subscription over one bad message
        }
      };
      es.onerror = () => {
        // Deliberately not relying on EventSource's own built-in retry: it
        // would reopen the *same* URL, and this URL's token is a snapshot
        // from connect time — stale after ~1h, the connection would just
        // fail 401 forever from then on. Reconnecting by hand gets a fresh
        // token every attempt instead.
        es?.close();
        if (!cancelled) retryTimer = setTimeout(connect, 3000);
      };
    }

    connect();
    return () => {
      cancelled = true;
      es?.close();
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [show]);

  return (
    <JobEventsContext.Provider value={{ pendingCount, registerPendingJob, lastEvent }}>
      {children}
    </JobEventsContext.Provider>
  );
}

export function useJobEvents(): JobEventsContextValue {
  const ctx = useContext(JobEventsContext);
  if (!ctx) throw new Error("useJobEvents must be used within JobEventsProvider");
  return ctx;
}
