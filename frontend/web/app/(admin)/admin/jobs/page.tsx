"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type AdminJobResponse } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  succeeded: "text-emerald-400",
  failed: "text-red-400",
  pending: "text-text-3",
  processing: "text-a3",
};

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJobResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .adminListJobs()
      .then(setJobs)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load jobs."));
  }, []);

  return (
    <div>
      <Link href="/admin" className="text-sm text-a3 hover:underline">
        ← Admin
      </Link>
      <h1 className="mt-2 font-display text-2xl font-bold">Job monitor</h1>
      <p className="mt-1.5 text-sm text-text-2">Last 100 jobs across every user, newest first.</p>

      {error && <p className="mt-6 text-sm text-red-400">{error}</p>}
      {!error && jobs === null && <p className="mt-6 text-sm text-text-3">Loading…</p>}
      {jobs && jobs.length === 0 && <p className="mt-6 text-sm text-text-3">No jobs yet.</p>}

      {jobs && jobs.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-2xl border border-border-soft">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border-soft bg-surface text-xs uppercase tracking-wide text-text-3">
              <tr>
                <th className="px-4 py-3 font-semibold">Created</th>
                <th className="px-4 py-3 font-semibold">User</th>
                <th className="px-4 py-3 font-semibold">Capability</th>
                <th className="px-4 py-3 font-semibold">Provider</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Cost</th>
                <th className="px-4 py-3 font-semibold">Visibility</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id} className="border-b border-border-soft last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 text-text-2">
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-text-2" title={job.user_id}>
                    {job.user_id.slice(0, 12)}…
                  </td>
                  <td className="px-4 py-3">{job.capability}</td>
                  <td className="px-4 py-3 text-text-2">{job.provider}</td>
                  <td className={`px-4 py-3 font-medium ${STATUS_COLOR[job.status] ?? ""}`}>
                    {job.status}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-text-2">
                    {job.actual_cost ?? job.estimated_cost}
                    {job.actual_cost === null && " (est.)"}
                  </td>
                  <td className="px-4 py-3 text-text-2">{job.visibility}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
