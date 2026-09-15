"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

/** Admin lives inside `frontend/web` now, not a separate deployment (ADR
 * 0020) — this is the app-level half of that decision's mitigation: wait
 * for Firebase auth, then check `GET /me`'s `role` (a Postgres column, not
 * a Firebase custom claim — there's nothing to check before this call
 * resolves) before rendering anything under `(admin)`. This is a UX
 * nicety (bounce a non-admin immediately, before any admin page fetches
 * anything) and the floor ADR 0020 accepted, not a claim of the same
 * protection a physically separate app would give — the real enforcement
 * is `require_admin` on every `/admin/*` backend route regardless of what
 * this does. */
export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [authorized, setAuthorized] = useState<boolean | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((me) => setAuthorized(me.role === "staff" || me.role === "admin"))
      .catch(() => setAuthorized(false));
  }, [loading, user, router]);

  useEffect(() => {
    if (authorized === false) router.replace("/app");
  }, [authorized, router]);

  if (loading || !user || authorized !== true) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-bg">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      <header className="flex items-center justify-between border-b border-border-soft px-6 py-4">
        <a href="/admin" className="font-display text-lg font-bold">
          Admin
        </a>
        <div className="flex items-center gap-4 text-sm text-text-2">
          <span className="hidden sm:inline">{user.email}</span>
          <a href="/app" className="text-a3 hover:underline">
            Back to app →
          </a>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">{children}</main>
    </div>
  );
}
