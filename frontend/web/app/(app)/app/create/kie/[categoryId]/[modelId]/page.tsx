"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, estimateKieCost, type KieModel } from "@/lib/api";
import { useJobEvents } from "@/lib/job-events";
import { useToast } from "@/components/Toast";

type FieldValue = string | number | boolean | string[];
type FormValues = Record<string, FieldValue>;

/** The generation page (ADR 0015/0016/0017) — schema-driven, not written
 * for any one model: every field it renders comes from
 * `KieModel.input_schema`. text/select/number/boolean/image are all
 * rendered; an "image" field's value is an array of URLs from
 * `api.uploadKieReference()`, uploaded as soon as each file is picked (see
 * `ImageField` below), never a raw File — by the time Generate is pressed,
 * `inputs` already only holds what Kie itself needs. `output_type` (image
 * or video so far) picks the result renderer in `KieResultView` — a future
 * audio category needs its own branch added there, per ADR 0015's design. */
export default function KieModelPage() {
  const router = useRouter();
  const params = useParams<{ modelId: string }>();
  const modelId = decodeURIComponent(params.modelId);

  const [model, setModel] = useState<KieModel | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [values, setValues] = useState<FormValues>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [shareToExplore, setShareToExplore] = useState(false);
  const { registerPendingJob } = useJobEvents();
  const { show } = useToast();
  // Every upload made on this page, whether or not it's still referenced by
  // a field's current value (e.g. the user removed it before submitting) —
  // sent along at submit time regardless, so the backend can still clean it
  // up once the job resolves (ADR 0016). An upload never submitted at all
  // (the user abandons the page) is a known, accepted gap — see the ADR.
  const uploadedR2Keys = useRef<string[]>([]);

  useEffect(() => {
    api
      .getKieModel(modelId)
      .then((m) => {
        setModel(m);
        const initial: FormValues = {};
        for (const field of m.input_schema) {
          if (field.type === "image") {
            initial[field.name] = [];
          } else if (field.default !== undefined) {
            initial[field.name] = field.default;
          }
        }
        setValues(initial);
      })
      .catch((err) => setLoadError(err instanceof ApiError ? err.message : "Couldn't load this model."));
  }, [modelId]);

  const renderableFields = useMemo(() => model?.input_schema ?? [], [model]);

  const canSubmit =
    model !== null &&
    renderableFields.every((f) => {
      if (!f.required) return true;
      const value = values[f.name];
      if (f.type === "image") return Array.isArray(value) && value.length > 0;
      return value !== undefined && value !== "";
    });

  const estimatedCost = model ? estimateKieCost(model.pricing, values) : null;

  async function handleGenerate() {
    if (!model || !canSubmit) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      // Defense in depth alongside the `number` input's own onBlur clamp
      // (above) — an Enter-to-submit doesn't reliably blur the focused
      // input first in every browser, so a value typed but never blurred
      // could otherwise still reach Kie unclamped. A no-op for `slider`
      // fields (a range input can't produce an out-of-range value to begin
      // with), harmless to include in the same loop.
      const clampedValues = { ...values };
      for (const f of model.input_schema) {
        if (f.type !== "number" && f.type !== "slider") continue;
        const raw = clampedValues[f.name];
        if (typeof raw !== "number" || Number.isNaN(raw)) continue;
        let clamped = raw;
        if (f.min !== undefined) clamped = Math.max(f.min, clamped);
        if (f.max !== undefined) clamped = Math.min(f.max, clamped);
        clampedValues[f.name] = clamped;
      }
      await api.submitKie(model.model_id, clampedValues, {
        visibility: shareToExplore ? "public" : "private",
        uploadedR2Keys: uploadedR2Keys.current,
      });
      // ADR 0018: submit, then get out of the way — Kie generation is
      // exactly the case that motivated this (image/video routinely take
      // well over a minute, previously spent staring at "Generating…"
      // right here). `/app/me` is where the result actually shows up,
      // pushed live via the SSE subscription `registerPendingJob` ties into.
      registerPendingJob();
      show("Submitted — we'll let you know when it's ready.", { tone: "success", href: "/app/me" });
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center gap-3 px-4 pb-3.5 pt-[18px]">
        <button
          onClick={() => router.back()}
          className="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-border-soft bg-surface"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text)" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <span className="font-display font-bold text-[16px]">{model?.display_name ?? "Loading…"}</span>
      </header>

      <div className="flex-1 px-4 pb-48">
        {loadError && (
          <div className="rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
            {loadError}
          </div>
        )}

        {model && (
          <div className="space-y-3">
            {renderableFields.map((field) => (
              <KieFormField
                key={field.name}
                field={field}
                value={values[field.name]}
                onChange={(v) => setValues((prev) => ({ ...prev, [field.name]: v }))}
                onUploaded={(r2Key) => uploadedR2Keys.current.push(r2Key)}
                disabled={submitting}
              />
            ))}

            {submitError && (
              <div className="rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
                {submitError}
              </div>
            )}

            <button
              onClick={() => setShareToExplore((v) => !v)}
              disabled={submitting}
              className="flex w-full items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5 text-left disabled:opacity-60"
            >
              <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-[10px] bg-a3/15 text-a3">
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="12" cy="12" r="9" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <path d="M12 3a15 15 0 010 18M12 3a15 15 0 000 18" />
                </svg>
              </div>
              <div className="flex-1">
                <div className="text-[13.5px] font-semibold">Share to Explore</div>
                <div className="mt-px text-[11.5px] text-text-2">Visible to everyone, no login required to view</div>
              </div>
              <div className={`h-[26px] w-11 flex-shrink-0 rounded-full transition-colors ${shareToExplore ? "grad-bg" : "bg-surface-2 border border-border"}`}>
                <div
                  className="h-[21px] w-[21px] rounded-full bg-white shadow transition-transform"
                  style={{ transform: shareToExplore ? "translate(20px, 2.5px)" : "translate(2.5px, 2.5px)" }}
                />
              </div>
            </button>
          </div>
        )}
      </div>

      {/* `bottom` matches `BottomNav`'s own real height (`h-16` + its own
       * `env(safe-area-inset-bottom)` padding) instead of a bare `bottom-16` —
       * on a phone with a home indicator, the nav grows taller than 64px, so
       * a bar pinned at exactly 64px from the true viewport edge sat *behind*
       * the now-taller nav (real bug, caught on a real phone) instead of
       * sitting just above it. */}
      <div
        className="fixed left-0 right-0 px-4 pb-4 pt-3"
        style={{
          bottom: "calc(4rem + env(safe-area-inset-bottom, 0px))",
          background: "linear-gradient(0deg, var(--bg) 65%, transparent)",
        }}
      >
        <button
          onClick={handleGenerate}
          disabled={submitting || !canSubmit}
          className="grad-bg flex w-full items-center justify-center gap-2 rounded-2xl py-3.5 text-sm font-semibold text-[#120a1c] disabled:opacity-50"
        >
          {submitting ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#120a1c]/30 border-t-[#120a1c]" />
              Submitting…
            </>
          ) : (
            `Generate${estimatedCost !== null ? ` · ${estimatedCost} credits` : ""}`
          )}
        </button>
      </div>
    </div>
  );
}

function KieFormField({
  field,
  value,
  onChange,
  onUploaded,
  disabled,
}: {
  field: KieModel["input_schema"][number];
  value: FieldValue | undefined;
  onChange: (value: FieldValue) => void;
  onUploaded: (r2Key: string) => void;
  disabled: boolean;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-text-2">
          {field.label}
          {field.required && <span className="text-danger"> *</span>}
        </span>
      </div>

      {field.type === "text" && (
        <textarea
          rows={4}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          placeholder={`Describe what you want…`}
          className="w-full resize-none rounded-2xl border border-border-soft bg-surface p-3.5 text-[14.5px] leading-relaxed outline-none placeholder:text-text-3"
        />
      )}

      {field.type === "slider" && (
        <div className="flex items-center gap-3">
          <input
            type="range"
            min={field.min ?? 0}
            max={field.max ?? 100}
            step={field.step ?? 1}
            value={(value as number) ?? field.default ?? field.min ?? 0}
            onChange={(e) => onChange(Number(e.target.value))}
            disabled={disabled}
            className="h-1.5 w-full flex-1 cursor-pointer appearance-none rounded-full bg-border-soft accent-a3"
          />
          {/* Read-only readout, deliberately not an input — a slider is the
              one control that can't produce an out-of-range value at all,
              which a free-text field paired with a `note` describing the
              range never actually guaranteed (ADR 0017, corrected after
              review of the shipped `number` version of this same field). */}
          <span className="w-8 flex-shrink-0 text-right text-[13.5px] tabular-nums text-text-1">
            {(value as number) ?? field.default ?? field.min ?? 0}
          </span>
        </div>
      )}

      {field.type === "number" && (
        <input
          type="number"
          min={field.min}
          max={field.max}
          value={(value as number) ?? ""}
          onChange={(e) => onChange(Number(e.target.value))}
          onBlur={(e) => {
            // Clamped on blur, not on every keystroke — clamping live would
            // fight a user typing a multi-digit number past `min` (e.g.
            // clearing "8" to type "12" would get shoved back to `min`
            // after the first keystroke). A `note` describing the range
            // (e.g. "Range: 1-15 seconds") never actually enforced it —
            // this does, once the user's done typing.
            const raw = Number(e.target.value);
            if (Number.isNaN(raw)) return;
            let clamped = raw;
            if (field.min !== undefined) clamped = Math.max(field.min, clamped);
            if (field.max !== undefined) clamped = Math.min(field.max, clamped);
            if (clamped !== raw) onChange(clamped);
          }}
          disabled={disabled}
          className="w-full rounded-2xl border border-border-soft bg-surface p-3.5 text-[14.5px] outline-none"
        />
      )}

      {field.type === "boolean" && (
        <button
          onClick={() => onChange(!value)}
          disabled={disabled}
          className="flex w-full items-center justify-between rounded-2xl border border-border-soft bg-surface px-4 py-3.5 disabled:opacity-60"
        >
          <span className="text-[13.5px]">{value ? "On" : "Off"}</span>
          <div className={`h-[26px] w-11 flex-shrink-0 rounded-full transition-colors ${value ? "grad-bg" : "bg-surface-2 border border-border"}`}>
            <div
              className="h-[21px] w-[21px] rounded-full bg-white shadow transition-transform"
              style={{ transform: value ? "translate(20px, 2.5px)" : "translate(2.5px, 2.5px)" }}
            />
          </div>
        </button>
      )}

      {field.type === "image" && (
        <ImageField
          value={(value as string[] | undefined) ?? []}
          onChange={onChange}
          onUploaded={onUploaded}
          max={field.max ?? (field.multiple ? 8 : 1)}
          disabled={disabled}
        />
      )}

      {field.type === "select" && field.options && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {field.options.map((option) => {
            // `numeric` fields (e.g. Veo's integer-enum `duration`) send a
            // real JSON number on selection, not the option's own string —
            // Kie's own validation expects that type, not a stringified one.
            const optionValue: FieldValue = field.numeric ? Number(option) : option;
            return (
              <button
                key={option}
                onClick={() => onChange(optionValue)}
                disabled={disabled}
                className={`flex-shrink-0 rounded-xl border px-3.5 py-2 text-[13px] font-medium ${
                  value === optionValue
                    ? "border-a3 bg-a3/15 text-a3"
                    : "border-border-soft bg-surface text-text-2"
                }`}
              >
                {option}
              </button>
            );
          })}
        </div>
      )}

      {field.note && <p className="mt-1.5 text-[11px] text-text-3">{field.note}</p>}
    </div>
  );
}

function ImageField({
  value,
  onChange,
  onUploaded,
  max,
  disabled,
}: {
  value: string[];
  onChange: (value: string[]) => void;
  onUploaded: (r2Key: string) => void;
  max: number;
  disabled: boolean;
}) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    const remaining = max - value.length;
    const selected = Array.from(files).slice(0, remaining);
    setUploading(true);
    setError(null);
    try {
      // Sequential, not Promise.all — a handful of reference images at
      // most (max 8), and this keeps a partial failure obvious (which one
      // failed) rather than an all-or-nothing Promise.all rejection.
      const newUrls: string[] = [];
      for (const file of selected) {
        const result = await api.uploadKieReference(file);
        onUploaded(result.r2_key);
        newUrls.push(result.url);
      }
      onChange([...value, ...newUrls]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  return (
    <div>
      {value.length > 0 && (
        <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
          {value.map((url, i) => (
            <div key={url} className="relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-xl border border-border-soft">
              {/* eslint-disable-next-line @next/next/no-img-element -- a public R2 URL (ADR 0016), not something next/image needs to optimize */}
              <img src={url} alt={`Reference ${i + 1}`} className="h-full w-full object-cover" />
              <button
                onClick={() => onChange(value.filter((_, j) => j !== i))}
                disabled={disabled}
                aria-label="Remove image"
                className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-black/60 text-white"
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {value.length < max && (
        <label className="flex items-center justify-center gap-2 rounded-2xl border border-dashed border-border-soft bg-surface px-4 py-3.5 text-[13px] text-text-2">
          {uploading ? (
            <>
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
              Uploading…
            </>
          ) : (
            `Add ${max > 1 ? "images" : "an image"} (${value.length}/${max})`
          )}
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple={max > 1}
            disabled={disabled || uploading}
            onChange={(e) => handleFiles(e.target.files)}
            className="hidden"
          />
        </label>
      )}

      {error && <p className="mt-1.5 text-[11px] text-danger">{error}</p>}
    </div>
  );
}

// The old inline "Your image/video is ready" result screen (media player +
// public/private toggle) is gone from here — ADR 0018 means this page
// never waits for a result to show one. That same pattern now lives on
// `/app/me`'s own job card, the one place results are actually viewed.
