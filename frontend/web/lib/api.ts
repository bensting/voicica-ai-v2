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

/** Same auth + error-unwrapping as request(), for the one endpoint that
 * sends a file (`POST /voice-models`) — a FormData body needs the browser
 * to set its own multipart boundary, so this deliberately never sets
 * Content-Type the way request() always does. */
async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  const token = await auth.currentUser?.getIdToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err = body?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "error",
      err?.message ?? `Request failed with ${res.status}`,
    );
  }
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
  // Shape depends on `capability` — tts vs. voice_model_training (ADR 0009)
  // have different input fields; both optional here rather than a
  // discriminated union, since every call site only ever reads one or two
  // fields of whichever job it already knows it has.
  input: {
    text?: string;
    voice_id?: string | null;
    voice_model_id?: string | null;
    speed?: number;
    volume?: number;
    pitch?: number;
    title?: string;
    reference_text?: string | null;
  };
  output: { asset_url?: string | null; voice_model_id?: string } | null;
  error: string | null;
  estimated_cost: number;
  actual_cost: number | null;
  visibility: "private" | "public";
  created_at: string;
  completed_at: string | null;
}

/** GET /gallery — one public creation (ADR 0010). Deliberately leaner than
 * JobResponse: no cost/error/visibility fields, no creator identity —
 * nothing a gallery viewer (possibly not the owner) needs. */
export interface GalleryItem {
  id: string;
  capability: string;
  provider: string;
  input: { text: string };
  output: { asset_url: string | null } | null;
  created_at: string;
}

export interface GalleryPage {
  items: GalleryItem[];
  next_cursor: string | null;
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

/** GET /voice-models — one of the current user's own cloned voices (ADR
 * 0009). Only `ready` ones are ever returned. `id` is what submitTts()'s
 * `voiceModelId` option expects — the voice_model_id counterpart to a
 * catalog Voice's `id`. `title` is the name given at training time —
 * always show it: an earlier version of this had no name at all, every
 * voice rendered as an identical placeholder, and that's exactly how a
 * real cloned voice got mistaken for test data and deleted. */
export interface VoiceModel {
  id: string;
  title: string;
  provider: string;
  state: string;
  created_at: string;
}

export const api = {
  me: () => request<MeResponse>("/me"),

  /** Defaults to "en"; callers on the (app) surface should pass
   * `getLocale()` from lib/locale.ts (ADR 0013) instead of relying on this
   * default. */
  getMenu: (locale: string = "en") =>
    request<MenuItem[]>(`/config/menu?locale=${encodeURIComponent(locale)}`),

  /** A voice is required by the backend (schemas.TTSRequest) — Fish Audio
   * isn't a general fallback, so there's no default to omit this for.
   * Exactly one of the two voice sources: `voiceId` (a catalog Voice's
   * `id`) or `voiceModelId` (a user's own cloned VoiceModel's `id`, ADR
   * 0009) — the backend routes to the right provider either way. `options`
   * (speed/volume/pitch, lib/audio-settings.ts — defaults to a no-op
   * 1.0/50/50 when omitted; visibility — ADR 0010, defaults to "private")
   * is otherwise optional. */
  submitTts: (
    text: string,
    voice: { voiceId: string } | { voiceModelId: string },
    options?: { speed: number; volume: number; pitch: number; visibility?: "private" | "public" },
  ) =>
    request<JobResponse>("/generate/tts", {
      method: "POST",
      body: JSON.stringify({
        text,
        voice_id: "voiceId" in voice ? voice.voiceId : undefined,
        voice_model_id: "voiceModelId" in voice ? voice.voiceModelId : undefined,
        ...options,
      }),
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

  /** GET /voice-models — the current user's own cloned voices (ADR 0009),
   * ready ones only. Feeds the Clone page's "Generate" tab and the
   * VoiceSheet-style picker there. */
  listVoiceModels: () => request<VoiceModel[]>("/voice-models"),

  /** POST /voice-models — train a new cloned voice from a short audio
   * sample. Multipart (not JSON, unlike every other endpoint here) because
   * it carries a file; returns a JobResponse like any other submission —
   * training turned out synchronous (Fish Audio's `train_mode="fast"`,
   * verified — backend/README.md), so the response is already terminal,
   * same as a TTS job. `referenceText` (what the sample audio says) is
   * optional but improves cloning quality, per Fish Audio's own docs. */
  trainVoiceModel: (title: string, audio: Blob, audioFileName: string, referenceText?: string) => {
    const formData = new FormData();
    formData.set("title", title);
    if (referenceText) formData.set("reference_text", referenceText);
    formData.set("audio", audio, audioFileName);
    return requestForm<JobResponse>("/voice-models", formData);
  },

  /** DELETE /voice-models/{id} — owner-only (ADR 0009); best-effort deletes
   * the model at Fish Audio too (services/voice_models.py), so this is
   * permanent, not a soft "hide" the user could undo. */
  deleteVoiceModel: (id: string) => request<void>(`/voice-models/${id}`, { method: "DELETE" }),

  /** Public — no auth needed (ADR 0010), though every call here still
   * carries a Bearer token since request() always attaches one when a user
   * is signed in; the backend just doesn't require it for this route. */
  getGallery: (cursor?: string) =>
    request<GalleryPage>(`/gallery${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),

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
