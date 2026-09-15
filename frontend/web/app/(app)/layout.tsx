"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { BottomNav } from "@/components/BottomNav";
import { APP_CONTENT_WIDTH } from "@/lib/layout";
import { ToastProvider } from "@/components/Toast";
import { JobEventsProvider } from "@/lib/job-events";

/** Every route under (app) requires login (product-scope.md §1.1) — gated
 * client-side against Firebase's auth state. A server-verified session-cookie
 * version of this is a reasonable later hardening step, not needed for this
 * slice (ADR 0005's route-group boundary is the structural piece; this is
 * just the runtime check inside it). */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-bg">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
      </div>
    );
  }

  return (
    <ToastProvider>
      <JobEventsProvider>
        {/* `min-h-dvh`, not `min-h-screen` (`100vh`) — on a mobile browser
         * whose address bar collapses/expands (most of them), `100vh` sizes
         * against the "large viewport" (as if the bar were always hidden),
         * so a `fixed bottom-0` descendant (`BottomNav`) can end up pinned
         * below the actually-visible area while the bar is still showing.
         * `dvh` tracks the real, current visual viewport instead. */}
        {/* Safe-area padding on both edges, in one place, so every page under
         * (app) gets it without each one's own <header>/bottom bar having to
         * ask for it individually — the same "fix it once at the shared
         * layout" move `viewport-fit=cover` itself was. `paddingBottom`
         * mirrors `BottomNav`'s own real height (its `h-16` content plus its
         * own `env(safe-area-inset-bottom)` padding) so scrolled-to-the-end
         * content on *any* (app) page clears the nav on a device with a home
         * indicator, not just on ones with no inset at all — the base `5rem`
         * (80px) is what this already reserved before real insets existed,
         * kept as the non-notched-device baseline rather than replaced by
         * the inset alone. Caught on a real phone: the "Generate speech"-
         * style fixed action bars a few create pages layer above the nav
         * (`bottom-16`, calibrated to the nav's un-padded 64px) don't read
         * this padding at all — they're `fixed`, not part of this flow —
         * and needed their own matching fix at each call site. */}
        <div
          className="min-h-dvh bg-bg"
          style={{
            paddingTop: "env(safe-area-inset-top, 0px)",
            paddingBottom: "calc(5rem + env(safe-area-inset-bottom, 0px))",
          }}
        >
          {/* Phone width by default, genuinely wider on desktop (`APP_CONTENT_
           * WIDTH`, `lib/layout.ts`) rather than just centering the same
           * phone-width column with empty space either side — a first pass
           * that did just that was correctly called out ("这样桌面端的客户就
           * 不用了吗？"). `BottomNav` uses the same width for its own inner
           * row so the nav stays visually aligned with the content above it
           * at every breakpoint. */}
          <div className={`mx-auto ${APP_CONTENT_WIDTH}`}>{children}</div>
          <BottomNav />
        </div>
      </JobEventsProvider>
    </ToastProvider>
  );
}
