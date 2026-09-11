"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

/**
 * `/` is reserved for the (marketing) route group once it exists
 * (product-scope.md §3 — not built yet). Until then, this is a placeholder
 * that just routes a visitor into the app or to sign in — not the marketing
 * homepage itself. Delete this file's redirect logic (not the route) when
 * (marketing)'s real homepage lands here.
 */
export default function RootRedirect() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    router.replace(user ? "/app" : "/login");
  }, [loading, user, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
    </div>
  );
}
