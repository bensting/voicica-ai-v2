"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError, type KieCategory, type KieModel } from "@/lib/api";
import { MenuIcon } from "@/components/icons";

/** A short price hint for the list row — the full live estimate
 * (`estimateKieCost`) needs real field values (a duration, a resolution
 * pick) this page doesn't have yet, so a rate-shaped price (ADR 0017)
 * shows its cheapest per-unit rate instead of a fabricated total. */
function priceHint(pricing: KieModel["pricing"]): string {
  if ("flat" in pricing) return `${pricing.flat} credits`;
  if ("rate_param" in pricing) {
    return `From ${Math.min(...Object.values(pricing.rates))} credits/sec`;
  }
  return `From ${Math.min(...Object.values(pricing.costs))} credits`;
}

/** The model-list page (ADR 0015) — generic over `categoryId`, not written
 * for "images" specifically: a new category (e.g. text-to-video) reuses
 * this exact page once its `kie_categories`/`kie_models` rows exist and a
 * capability-menu item points here, no frontend change needed. Only the
 * icon below is a hardcoded stand-in until more than one output_type
 * exists to actually distinguish. */
export default function KieCategoryPage() {
  const router = useRouter();
  const params = useParams<{ categoryId: string }>();
  const categoryId = decodeURIComponent(params.categoryId);

  const [category, setCategory] = useState<KieCategory | null>(null);
  const [models, setModels] = useState<KieModel[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getKieCategories().then((cats) => {
      setCategory(cats.find((c) => c.id === categoryId) ?? null);
    }).catch(() => {});
    api
      .getKieModels(categoryId)
      .then(setModels)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Something went wrong."));
  }, [categoryId]);

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
        <span className="font-display font-bold text-[16px]">{category?.display_name ?? "Choose a model"}</span>
      </header>

      <div className="flex-1 px-4 pb-8 space-y-2">
        {models === null && !error && (
          <div className="flex justify-center py-10">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-border-soft border-t-a3" />
          </div>
        )}
        {error && (
          <div className="rounded-xl border border-danger/25 bg-danger/10 px-3.5 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}
        {models?.length === 0 && (
          <p className="py-10 text-center text-sm text-text-2">No models available yet.</p>
        )}
        {models?.map((model) => (
          <Link
            key={model.model_id}
            href={`/app/create/kie/${encodeURIComponent(categoryId)}/${encodeURIComponent(model.model_id)}`}
            className="flex items-center gap-3 rounded-2xl border border-border-soft bg-surface px-4 py-3.5"
          >
            <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full bg-surface-2 text-text-2">
              <MenuIcon name={model.output_type === "video" ? "video" : "image"} width={16} height={16} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13.5px] font-medium">{model.display_name}</div>
              <div className="mt-0.5 truncate text-[11.5px] text-text-2">{priceHint(model.pricing)}</div>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-3)" strokeWidth="2" className="shrink-0">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </Link>
        ))}
      </div>
    </div>
  );
}
