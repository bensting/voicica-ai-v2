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
  input: { text: string; voice_id: string | null };
  output: { asset_url: string | null } | null;
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

/** GET /catalog/voices — one synced voice (ADR 0007). `id` is what
 * submitTts()'s voiceId param expects. Consumed by components/VoiceSheet.tsx. */
export interface Voice {
  id: string;
  provider: "azure" | "google" | "fish_audio";
  locale: string;
  display_name: string;
  gender: string | null;
  styles: string[] | null;
}

/** GET /catalog/languages — one selectable base language ("es", not
 * "es-MX"), with how many voices it has across every provider/locale
 * variant combined. Grouped by base language, not exact locale, because
 * providers don't carve a language into countries the same way (Azure has
 * ~22 Spanish locales, Google has 2) — a locale-level picker would really
 * just be Azure's taxonomy. Populates the picker's dropdown cheaply,
 * without fetching every voice just to read off `.locale`. */
export interface LanguageOption {
  language: string;
  voice_count: number;
}

export const api = {
  me: () => request<MeResponse>("/me"),

  /** Defaults to "en"; callers on the (app) surface should pass
   * `getLocale()` from lib/locale.ts (ADR 0013) instead of relying on this
   * default. */
  getMenu: (locale: string = "en") =>
    request<MenuItem[]>(`/config/menu?locale=${encodeURIComponent(locale)}`),

  submitTts: (text: string, voiceId?: string) =>
    request<JobResponse>("/generate/tts", {
      method: "POST",
      body: JSON.stringify({ text, voice_id: voiceId ?? null }),
    }),

  /** Every base language actually present in the catalog (83 across
   * Azure/Google — no target-market restriction, see
   * backend/app/services/voice_catalog.py's module docstring for why).
   * Cheap: counts, not full voice objects. */
  getLanguages: (provider?: string) =>
    request<LanguageOption[]>(`/catalog/languages${provider ? `?provider=${encodeURIComponent(provider)}` : ""}`),

  /** `language` prefix-matches a base language ("es" -> every es-* locale,
   * from every provider) — what the picker uses, so switching languages
   * never misses a provider's voices just because its locale code for that
   * language happens to differ. `locale` is an exact match, for the rare
   * case something wants one specific provider-specific variant. Always
   * pass one or the other from the picker — the full catalog is ~2800
   * voices across every language Azure/Google support. */
  getVoices: (provider?: string, options?: { locale?: string; language?: string }) => {
    const params = new URLSearchParams();
    if (provider) params.set("provider", provider);
    if (options?.locale) params.set("locale", options.locale);
    if (options?.language) params.set("language", options.language);
    const qs = params.toString();
    return request<Voice[]>(`/catalog/voices${qs ? `?${qs}` : ""}`);
  },

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
