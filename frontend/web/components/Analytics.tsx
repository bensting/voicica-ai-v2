"use client";

import { logEvent } from "firebase/analytics";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { getFirebaseAnalytics } from "@/lib/firebase";

/** GA4 via Firebase Analytics (ADR 0021) — mounted once per marketing
 * surface ((marketing)'s layout and `/get`'s layout, not the authenticated
 * app/admin). Next.js client-side navigation never fires a real page load,
 * so `page_view` has to be logged by hand on every pathname change —
 * Firebase Analytics doesn't do this for an SPA automatically the way a
 * plain `gtag.js` snippet dropped into a classic multi-page site would. */
export function Analytics() {
  const pathname = usePathname();

  useEffect(() => {
    getFirebaseAnalytics().then((analytics) => {
      if (analytics) logEvent(analytics, "page_view", { page_path: pathname });
    });
  }, [pathname]);

  return null;
}

/** Fire-and-forget — a dropped/late analytics event must never delay or
 * block the actual navigation (Play Store / sign-in) it's measuring, so
 * this is called from an onClick and never awaited. */
export function logCtaClick(cta: "download_android" | "get_started_web"): void {
  getFirebaseAnalytics().then((analytics) => {
    if (analytics) logEvent(analytics, "select_content", { content_type: "cta", item_id: cta });
  });
}
