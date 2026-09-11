"use client";

import { useEffect, useState } from "react";
import { api, type JobResponse, type MeResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";

export default function MePage() {
  const { user, signOut } = useAuth();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [jobs, setJobs] = useState<JobResponse[] | null>(null);

  useEffect(() => {
    api.me().then(setMe).catch(() => setMe(null));
    api.listJobs().then(setJobs).catch(() => setJobs([]));
  }, []);

  const publicCount = jobs?.filter((j) => j.visibility === "public").length ?? null;

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[8%] -right-[14%] w-[60%] h-[30%] rounded-full bg-a1/15 blur-[90px]" />
      </div>

      <header className="relative flex items-center gap-3.5 px-5 pb-1.5 pt-6">
        <div className="grad-bg flex h-[54px] w-[54px] items-center justify-center rounded-full font-display text-xl font-bold text-[#120a1c]">
          {(user?.email ?? "?").charAt(0).toUpperCase()}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-[17px] font-bold truncate">
            {user?.displayName ?? "Your account"}
          </div>
          <div className="mt-0.5 truncate text-xs text-text-2">{user?.email}</div>
        </div>
        <button
          onClick={() => signOut()}
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[10px] border border-border-soft bg-surface text-text-2"
          title="Sign out"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
            <polyline points="16,17 21,12 16,7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
        </button>
      </header>

      <div className="relative mx-5 mt-4 flex items-center justify-between rounded-[20px] border border-border-soft bg-surface p-4.5">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-text-3">Balance</div>
          <div className="mt-0.5 font-display text-[26px] font-bold tabular-nums">
            {me ? me.balance.toLocaleString() : "…"}
          </div>
        </div>
        <button className="grad-bg rounded-xl px-4 py-2.5 text-[13px] font-semibold text-[#120a1c]">
          Top up
        </button>
      </div>

      <div className="relative mx-5 mt-2.5 grid grid-cols-2 gap-2.5">
        <StatTile label="Creations" value={jobs?.length ?? null} />
        <StatTile label="Public" value={publicCount} />
      </div>

      <section className="relative px-5 pt-6 pb-4">
        <h2 className="mb-2 font-display text-[15px] font-bold">History</h2>
        {jobs === null && (
          <div className="flex justify-center py-8">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}
        {jobs?.length === 0 && (
          <p className="py-6 text-center text-sm text-text-2">No creations yet.</p>
        )}
        <div className="flex flex-col gap-2">
          {jobs?.map((job) => (
            <div
              key={job.id}
              className="flex items-center gap-3 rounded-2xl border border-border-soft bg-surface p-3"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium">{job.input.text}</div>
                <div className="mt-0.5 text-[11px] text-text-2">
                  {job.provider} · {new Date(job.created_at).toLocaleDateString()}
                </div>
              </div>
              <span
                className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${
                  job.visibility === "public" ? "text-success bg-success/10" : "text-text-2 bg-white/5"
                }`}
              >
                {job.visibility === "public" ? "Public" : "Private"}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-2xl border border-border-soft bg-surface px-3 py-3 text-center">
      <div className="font-display text-lg font-bold tabular-nums">{value ?? "…"}</div>
      <div className="mt-0.5 text-[10.5px] text-text-2">{label}</div>
    </div>
  );
}
