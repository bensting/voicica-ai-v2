"use client";

import { auth } from "./firebase";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

/** Every call goes through here — attaches the current Firebase ID token
 * (docs/api-contract.md "Conventions": Bearer auth) and unwraps the
 * {"error": {code, message}} envelope into a typed ApiError. */
async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await auth.currentUser?.getIdToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err = body?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "error",
      err?.message ?? `Request failed with ${res.status}`,
    );
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ---- Shapes mirroring backend/app/api/schemas.py ----

export interface MeResponse {
  id: string;
  email: string;
  role: string;
  balance: number;
}

export interface JobResponse {
  id: string;
  capability: string;
  provider: string;
  status: "pending" | "processing" | "succeeded" | "failed";
  input: { text: string; reference_id: string | null };
  output: { asset_url: string | null; reference_id: string | null } | null;
  error: string | null;
  estimated_cost: number;
  actual_cost: number | null;
  visibility: "private" | "public";
  created_at: string;
  completed_at: string | null;
}

export interface MenuItem {
  id: string;
  icon: string;
  route: string;
  badge: string | null;
  label: string;
  description: string;
}

export const api = {
  me: () => request<MeResponse>("/me"),

  /** locale hardcoded to "en" until the i18n routing strategy is decided —
   * wire this to the active locale then (lib/api.ts is the only place that
   * needs to change). */
  getMenu: (locale: string = "en") =>
    request<MenuItem[]>(`/config/menu?locale=${encodeURIComponent(locale)}`),

  submitTts: (text: string, referenceId?: string) =>
    request<JobResponse>("/generate/tts", {
      method: "POST",
      body: JSON.stringify({ text, reference_id: referenceId ?? null }),
    }),

  listJobs: () => request<JobResponse[]>("/jobs"),

  getJob: (id: string) => request<JobResponse>(`/jobs/${id}`),

  setVisibility: (id: string, visibility: "public" | "private") =>
    request<JobResponse>(`/jobs/${id}?visibility=${visibility}`, {
      method: "PATCH",
    }),

  /** `output.asset_url` is a path on our own API (proxying R2 — see backend
   * services/assets.py), so it needs the same auth header as everything
   * else; this fetches it as a Blob URL for an <audio>/<a download> element,
   * since neither can attach an Authorization header itself. */
  assetBlobUrl: async (assetUrl: string): Promise<string> => {
    const token = await auth.currentUser?.getIdToken();
    const res = await fetch(`${API_BASE}${assetUrl}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "error", "Failed to load asset.");
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },
};
