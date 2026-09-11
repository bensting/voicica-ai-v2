"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type JobResponse } from "@/lib/api";
import { CreditsPill } from "@/components/CreditsPill";

export default function HomePage() {
  const [jobs, setJobs] = useState<JobResponse[] | null>(null);

  useEffect(() => {
    api.listJobs().then(setJobs).catch(() => setJobs([]));
  }, []);

  return (
    <div className="relative">
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="absolute -top-[8%] -left-[10%] w-[60%] h-[30%] rounded-full bg-a1/15 blur-[90px]" />
      </div>

      <header className="relative flex items-center justify-between px-5 pt-6 pb-2">
        <div className="flex items-center gap-2.5">
          <div className="h-[30px] w-[30px] rounded-[9px] grad-bg flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0a0a1a" strokeWidth="2.2" strokeLinecap="round">
              <path d="M12 3v9" />
              <path d="M8 8c0 4 1.8 6 4 6s4-2 4-6" />
              <path d="M12 17v4" />
            </svg>
          </div>
          <span className="font-display font-bold text-[17px] tracking-tight">Voicica</span>
        </div>
        <CreditsPill />
      </header>

      <section className="relative px-5 pt-6">
        <div className="flex items-baseline justify-between">
          <h2 className="font-display font-bold text-[15px]">Your creations</h2>
          <Link href="/create/tts" className="text-xs font-semibold text-a3">
            + New
          </Link>
        </div>

        {jobs === null && (
          <div className="mt-4 flex justify-center py-10">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}

        {jobs?.length === 0 && (
          <div className="mt-4 flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-12 text-center">
            <p className="text-sm text-text-2 max-w-[220px]">
              Nothing here yet — your first generation will show up in this list.
            </p>
            <Link
              href="/create/tts"
              className="grad-bg rounded-xl px-4 py-2 text-xs font-semibold text-[#120a1c]"
            >
              Generate speech
            </Link>
          </div>
        )}

        <div className="mt-3 flex flex-col gap-2">
          {jobs?.map((job) => (
            <JobRow key={job.id} job={job} />
          ))}
        </div>
      </section>
    </div>
  );
}

function JobRow({ job }: { job: JobResponse }) {
  const statusStyle: Record<string, string> = {
    succeeded: "text-success bg-success/10",
    failed: "text-danger bg-danger/10",
    pending: "text-a5 bg-a5/10",
    processing: "text-a5 bg-a5/10",
  };

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border-soft bg-surface p-3">
      <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-surface-2 text-a3">
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7">
          <path d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
          <path d="M19 10v2a7 7 0 01-14 0v-2" />
        </svg>
      </div>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium">{job.input.text}</div>
        <div className="mt-0.5 text-[11px] text-text-2">
          {job.provider} · {new Date(job.created_at).toLocaleString()}
        </div>
      </div>
      <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${statusStyle[job.status] ?? ""}`}>
        {job.status}
      </span>
    </div>
  );
}
