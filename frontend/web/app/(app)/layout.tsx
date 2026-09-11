"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { BottomNav } from "@/components/BottomNav";

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
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg pb-20">
      {children}
      <BottomNav />
    </div>
  );
}
