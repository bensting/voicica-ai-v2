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
  // vs. a Kie job (ADR 0015) have different input fields; all optional here
  // rather than a discriminated union, since every call site only ever
  // reads the field(s) of whichever job it already knows it has.
  input: {
    text?: string;
    voice_id?: string | null;
    voice_model_id?: string | null;
    speed?: number;
    volume?: number;
    pitch?: number;
    title?: string;
    reference_text?: string | null;
    // Kie job (services/jobs.py submit_kie_job): `inputs` is whatever that
    // model's `input_schema` declared, passed through verbatim.
    model_id?: string;
    inputs?: Record<string, string | number | boolean | string[]>;
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
  // `text` (TTS) vs. `inputs.prompt` (a Kie job, ADR 0015) — the shape
  // depends on `capability`/`provider`, same reasoning as JobResponse.input.
  input: { text?: string; inputs?: Record<string, string | number | boolean | string[]> };
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

/** GET /kie/categories (ADR 0015) — one Kie capability category, e.g.
 * "text-to-image". `output_type` picks which result renderer a category's
 * jobs need — only "image" is handled today (app/create/kie/[id]/[modelId]),
 * same restriction called out in the ADR. */
export interface KieCategory {
  id: string;
  display_name: string;
  output_type: "image" | "video" | "audio";
}

/** One field of a Kie model's schema-driven form (ADR 0015/0016). An
 * "image" field means one or more reference photos (`multiple`, `max`
 * caps how many — every model catalogued so far allows up to 8): the
 * generation page uploads each one via `api.uploadKieReference()` as soon
 * as it's picked, so by submission time this field's value is already the
 * real URL(s) Kie needs, not a File. */
export interface KieInputField {
  name: string;
  label: string;
  type: "text" | "select" | "number" | "boolean" | "image" | "slider";
  options?: string[];
  default?: string | number | boolean;
  required?: boolean;
  note?: string;
  multiple?: boolean;
  // `image`: max number of files. `slider`/`number`: upper bound on the
  // value (paired with `min` below) — same field name, meaning depends on
  // `type`, same pattern `default`/`options` already follow.
  max?: number;
  // `slider`/`number` only: lower bound. A genuine continuous range (e.g.
  // Grok's `duration`, 1-15 seconds) should be a `slider`, not a free-text
  // `number` (ADR 0017, corrected after review) — a slider can't produce
  // an out-of-range value at all (the browser clamps the drag itself),
  // where a text field only describing its range in `note` never actually
  // enforced it. `number` (with `min`/`max` still respected, on blur) stays
  // available for a value someone would need to type rather than drag.
  min?: number;
  // `slider` only: step size between values. Defaults to 1.
  step?: number;
  // `select` only: Kie expects a real JSON number for this field (e.g.
  // Veo's `duration`, an integer enum), not the string an option button
  // would otherwise send — coerce on selection instead of leaving the
  // caller to type a free-form number that Kie's own validation may
  // reject (ADR 0017: a `type: "number"` free-text field let a user type
  // an out-of-range value like 5 or 7 with no feedback until submission).
  numeric?: boolean;
}

/** The credit-hold estimate only (ADR 0015/0017) — settlement always uses
 * Kie's own reported cost, never this. Three shapes: a flat price, one
 * field's value looked up in a table (e.g. `resolution`), or a per-unit
 * rate looked up by one field and multiplied by another (e.g.
 * credits-per-second-of-video by resolution). */
export type KiePricing =
  | { flat: number }
  | { param: string; costs: Record<string, number>; default?: string }
  | { rate_param: string; tier_param: string; rates: Record<string, number>; default?: string };

/** POST /kie/uploads (ADR 0016) — a short-lived public URL for one
 * reference image, plus its R2 key (only needed so the job that ends up
 * using it can be told to clean it up — see `api.submitKie`). */
export interface KieUploadResult {
  url: string;
  r2_key: string;
}

/** GET /kie/models(/:model_id) — one catalogued model. `model_id` is Kie's
 * own real string and may contain a literal "/" (e.g.
 * "flux-2/pro-text-to-image") — always percent-encode it in a URL. */
export interface KieModel {
  model_id: string;
  category_id: string;
  display_name: string;
  // Denormalized from this model's category (ADR 0017) — which result
  // renderer the generation page should use, without a second fetch.
  output_type: "image" | "video" | "audio";
  input_schema: KieInputField[];
  pricing: KiePricing;
}

/** Mirrors backend/app/services/kie_catalog.py's estimate_cost() — an
 * estimate for display only, purely client-side; the real hold amount is
 * always computed server-side at submission. */
export function estimateKieCost(pricing: KiePricing, values: Record<string, unknown>): number {
  if ("flat" in pricing) return pricing.flat;
  if ("rate_param" in pricing) {
    const tierValue = String(values[pricing.tier_param] ?? pricing.default ?? "");
    const rate = pricing.rates[tierValue] ?? Math.min(...Object.values(pricing.rates));
    const amount = Number(values[pricing.rate_param]) || 0;
    return Math.ceil(rate * amount);
  }
  const value = String(values[pricing.param] ?? pricing.default ?? "");
  return pricing.costs[value] ?? Math.min(...Object.values(pricing.costs));
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
  // `outputType` splits Explore into tabs (Voices/Images/Videos) — reuses
  // the same audio/image/video vocabulary `KieModel.output_type` already
  // carries, filtered server-side (`GET /gallery`'s own query, not a
  // client-side filter) so pagination stays correct per tab.
  getGallery: (options?: { cursor?: string; outputType?: "audio" | "image" | "video" }) => {
    const params = new URLSearchParams();
    if (options?.cursor) params.set("cursor", options.cursor);
    if (options?.outputType) params.set("output_type", options.outputType);
    const qs = params.toString();
    return request<GalleryPage>(`/gallery${qs ? `?${qs}` : ""}`);
  },

  getJob: (id: string) => request<JobResponse>(`/jobs/${id}`),

  /** Poll `GET /jobs/{id}` until it reaches a terminal status — genuinely
   * necessary now (ADR 0014): the provider call happens in a background
   * worker, so `submitTts()`/`trainVoiceModel()`'s own response is always
   * `pending`, never already-finished the way it used to be. Every real
   * provider call this app makes today finishes in a few seconds, so a
   * short fixed interval (no exponential backoff) keeps this feeling
   * close to instant without hammering the API. Throws `ApiError` (code
   * "job_timeout") if nothing terminal shows up within `timeoutMs` — the
   * job itself keeps running server-side either way; this is just giving
   * up on waiting for it in this tab. */
  pollJob: async (
    id: string,
    { intervalMs = 800, timeoutMs = 60_000 }: { intervalMs?: number; timeoutMs?: number } = {},
  ): Promise<JobResponse> => {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const job = await request<JobResponse>(`/jobs/${id}`);
      if (job.status === "succeeded" || job.status === "failed") return job;
      if (Date.now() >= deadline) {
        throw new ApiError(408, "job_timeout", "This is taking longer than expected.");
      }
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
  },

  setVisibility: (id: string, visibility: "public" | "private") =>
    request<JobResponse>(`/jobs/${id}?visibility=${visibility}`, {
      method: "PATCH",
    }),

  /** GET /kie/categories (ADR 0015) — the enabled Kie capability categories.
   * Backs the model-list page's header; not the capability menu itself
   * (that's still GET /config/menu — a category only ever appears there
   * once an admin adds a menu item pointing at its route, same as any other
   * capability). */
  getKieCategories: () => request<KieCategory[]>("/kie/categories"),

  /** GET /kie/models?category_id= — every enabled model in one category.
   * Feeds the model-list page (app/create/kie/[categoryId]). */
  getKieModels: (categoryId: string) =>
    request<KieModel[]>(`/kie/models?category_id=${encodeURIComponent(categoryId)}`),

  /** GET /kie/models/{model_id} — one model's full schema, for the
   * generation page (app/create/kie/[categoryId]/[modelId]). `modelId` may
   * contain a literal "/" (e.g. "flux-2/pro-text-to-image") — always
   * encoded here, never assumed to be a single clean path segment. */
  getKieModel: (modelId: string) => request<KieModel>(`/kie/models/${encodeURIComponent(modelId)}`),

  /** POST /kie/uploads (ADR 0016) — uploads one reference image to a
   * short-lived public R2 URL Kie's own servers can fetch (a "select a
   * file" image field's value is never the File itself, always this call's
   * `url`). Called once per file as soon as it's picked, not deferred to
   * submission time. */
  uploadKieReference: (file: File) => {
    const formData = new FormData();
    formData.set("file", file);
    return requestForm<KieUploadResult>("/kie/uploads", formData);
  },

  /** POST /generate/kie (ADR 0015/0016) — one endpoint for every Kie model.
   * Genuinely async under the hood (unlike TTS): the response is always
   * `pending`, never already-finished — poll with pollJob() same as any
   * other job. `inputs` is passed through to Kie verbatim, shaped by
   * whatever `KieModel.input_schema` this model_id declared — an "image"
   * field's value is a URL (or array of URLs) from `uploadKieReference()`,
   * never a raw File. `uploadedR2Keys` are those same uploads' own keys,
   * tracked only so the backend can delete them once this job finishes
   * (ADR 0016) — omit for a model with no image field. */
  submitKie: (
    modelId: string,
    inputs: Record<string, string | number | boolean | string[]>,
    options?: { visibility?: "private" | "public"; uploadedR2Keys?: string[] },
  ) =>
    request<JobResponse>("/generate/kie", {
      method: "POST",
      body: JSON.stringify({
        model_id: modelId,
        inputs,
        visibility: options?.visibility ?? "private",
        uploaded_r2_keys: options?.uploadedR2Keys ?? [],
      }),
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
