"""Read/write access to `kie_categories`/`kie_models` (ADR 0015) — the
hand-curated catalog `providers/kie.py` and the generic `/generate/kie`
route are driven by. Real tables (not `app_settings`, unlike
`capability_menu`) because this grows one row at a time, the same shape as
`voice_catalog` — see ADR 0015's Decision for why.

`_SEED_CATEGORIES`/`_SEED_MODELS` are the actual first real data (verified
against Kie's live site, not placeholders) — kept here, not only in the
migration, so this module is the one place to read to see what's in the
catalog without needing DB access, same convention as `menu.py`'s
`_DEFAULT_ITEMS`. The migration (`0009_kie_catalog.py`) bulk-inserts these
constants; adding a new model afterward is a normal INSERT (via the admin
routes below), not a code change or a new migration.
"""

import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import KieCategory, KieModel

_SEED_CATEGORIES: list[dict[str, Any]] = [
    {"id": "text-to-image", "display_name": "Text to Image", "output_type": "image", "enabled": True},
    {"id": "image-to-image", "display_name": "Image to Image", "output_type": "image", "enabled": True},
    {"id": "image-to-video", "display_name": "Image to Video", "output_type": "video", "enabled": True},
]

# Pricing numbers are Kie's own real, currently-displayed credit counts
# (verified live, 2026-09-12) — not invented, and not yet marked up (ADR
# 0015: no margin layer exists yet, these ARE the settlement unit for now).
_SEED_MODELS: list[dict[str, Any]] = [
    {
        "model_id": "flux-2/pro-text-to-image",
        "provider_model_id": "flux-2/pro-text-to-image",
        "fixed_inputs": {},
        "category_id": "text-to-image",
        "display_name": "Flux-2 — Pro",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                "default": "1:1",
                "required": True,
            },
            {
                # Confirmed required by a real `createTask` call against
                # this exact model (2026-09-12): omitting it returns "Kie
                # 500: resolution is required" — not visible on Kie's own
                # simplified playground Form view, only found by actually
                # calling the API (see this project's own convention: verify
                # against the real call, don't trust a summarized doc/UI).
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                "options": ["1K", "2K"],
                "default": "1K",
                "required": True,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"1K": 5, "2K": 7}, "default": "1K"},
        "enabled": True,
    },
    {
        "model_id": "flux-2/flex-text-to-image",
        "provider_model_id": "flux-2/flex-text-to-image",
        "fixed_inputs": {},
        "category_id": "text-to-image",
        "display_name": "Flux-2 — Flex",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                "default": "1:1",
                "required": True,
            },
            {"name": "resolution", "label": "Resolution", "type": "select", "options": ["1K", "2K"],
             "default": "1K", "required": True},
        ],
        # Flex's own pricing wasn't captured (only Pro's "Model Type" tab was
        # checked live) — starting disabled rather than guessing a number
        # that would silently either overcharge or underprice a real user.
        "pricing": {"flat": 5},
        "enabled": False,
    },
    {
        "model_id": "gpt-image-2-5-flare-text-to-image",
        "provider_model_id": "gpt-image-2-5-flare-text-to-image",
        "fixed_inputs": {},
        "category_id": "text-to-image",
        "display_name": "GPT Image 2.5 — Flare",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "21:16", "16:27", "9:8", "8:9"],
                "default": "auto",
                "required": False,
                # Real constraint, not modeled (ADR 0015): Kie rejects
                # resolution=2K/4K for the 21:16/16:27/9:8/8:9 ratios — an
                # invalid combination fails at Kie, refunded like any other
                # failed job, rather than being pre-validated here.
                "note": "21:16, 16:27, 9:8 and 8:9 support 1K resolution only.",
            },
            {
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                "options": ["1K", "2K", "4K"],
                "default": "1K",
                "required": False,
            },
            {
                "name": "background",
                "label": "Background",
                "type": "select",
                "options": ["transparent", "opaque", "auto"],
                "default": "auto",
                "required": False,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"1K": 6, "2K": 10, "4K": 16}, "default": "1K"},
        "enabled": True,
    },
    # ---- image-to-image (ADR 0016) — same 4 model families as above, their
    # image-to-image sibling model_id. Verified live: all four take the same
    # real field name `input_urls` (array of URLs Kie's own servers fetch —
    # never a file upload or base64, see ADR 0016) alongside `prompt`, so
    # this isn't per-vendor guesswork. Pricing numbers are each model's own
    # text-to-image sibling's numbers — the pricing banner on Kie's site is
    # shared across every Model Type tab on the same page, confirming it's
    # the same rate. ----
    {
        "model_id": "flux-2/pro-image-to-image",
        "provider_model_id": "flux-2/pro-image-to-image",
        "fixed_inputs": {},
        "category_id": "image-to-image",
        "display_name": "Flux-2 — Pro",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "input_urls",
                "label": "Reference images",
                "type": "image",
                "multiple": True,
                "max": 8,
                "required": True,
            },
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                "default": "1:1",
                "required": True,
            },
            {"name": "resolution", "label": "Resolution", "type": "select", "options": ["1K", "2K"],
             "default": "1K", "required": True},
            {
                "name": "nsfw_checker",
                "label": "NSFW filter",
                "type": "boolean",
                "default": True,
                "required": False,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"1K": 5, "2K": 7}, "default": "1K"},
        "enabled": True,
    },
    {
        "model_id": "flux-2/flex-image-to-image",
        "provider_model_id": "flux-2/flex-image-to-image",
        "fixed_inputs": {},
        "category_id": "image-to-image",
        "display_name": "Flux-2 — Flex",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "input_urls",
                "label": "Reference images",
                "type": "image",
                "multiple": True,
                "max": 8,
                "required": True,
            },
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["1:1", "4:3", "3:4", "16:9", "9:16", "3:2", "2:3"],
                "default": "1:1",
                "required": True,
            },
            {"name": "resolution", "label": "Resolution", "type": "select", "options": ["1K", "2K"],
             "default": "1K", "required": True},
            {
                "name": "nsfw_checker",
                "label": "NSFW filter",
                "type": "boolean",
                "default": True,
                "required": False,
            },
        ],
        # Same caveat as flux-2/flex-text-to-image: Flex's own pricing wasn't
        # independently captured — disabled rather than guessing.
        "pricing": {"flat": 5},
        "enabled": False,
    },
    {
        "model_id": "gpt-image-2-5-flare-image-to-image",
        "provider_model_id": "gpt-image-2-5-flare-image-to-image",
        "fixed_inputs": {},
        "category_id": "image-to-image",
        "display_name": "GPT Image 2.5 — Flare",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "input_urls",
                "label": "Reference images",
                "type": "image",
                "multiple": True,
                "max": 8,
                "required": True,
            },
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "21:16", "16:27", "9:8", "8:9"],
                "default": "auto",
                "required": False,
                "note": "21:16, 16:27, 9:8 and 8:9 support 1K resolution only.",
            },
            {
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                "options": ["1K", "2K", "4K"],
                "default": "1K",
                "required": False,
            },
            {
                "name": "background",
                "label": "Background",
                "type": "select",
                "options": ["transparent", "opaque", "auto"],
                "default": "auto",
                "required": False,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"1K": 6, "2K": 10, "4K": 16}, "default": "1K"},
        "enabled": True,
    },
    {
        "model_id": "gpt-image-2-5-sunburst-image-to-image",
        "provider_model_id": "gpt-image-2-5-sunburst-image-to-image",
        "fixed_inputs": {},
        "category_id": "image-to-image",
        "display_name": "GPT Image 2.5 — Sunburst",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "input_urls",
                "label": "Reference images",
                "type": "image",
                "multiple": True,
                "max": 8,
                "required": True,
            },
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "21:16", "16:27", "9:8", "8:9"],
                "default": "auto",
                "required": False,
                "note": "21:16, 16:27, 9:8 and 8:9 support 1K resolution only.",
            },
            {
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                "options": ["1K", "2K", "4K"],
                "default": "1K",
                "required": False,
            },
            {
                "name": "background",
                "label": "Background",
                "type": "select",
                "options": ["transparent", "opaque", "auto"],
                "default": "auto",
                "required": False,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"1K": 6, "2K": 10, "4K": 16}, "default": "1K"},
        "enabled": True,
    },
    {
        "model_id": "gpt-image-2-5-sunburst-text-to-image",
        "provider_model_id": "gpt-image-2-5-sunburst-text-to-image",
        "fixed_inputs": {},
        "category_id": "text-to-image",
        "display_name": "GPT Image 2.5 — Sunburst",
        # Same form shape as Flare (both share this page's schema/pricing on
        # Kie's site) — not independently re-verified per variant.
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["auto", "1:1", "3:2", "2:3", "16:9", "9:16", "21:16", "16:27", "9:8", "8:9"],
                "default": "auto",
                "required": False,
                "note": "21:16, 16:27, 9:8 and 8:9 support 1K resolution only.",
            },
            {
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                "options": ["1K", "2K", "4K"],
                "default": "1K",
                "required": False,
            },
            {
                "name": "background",
                "label": "Background",
                "type": "select",
                "options": ["transparent", "opaque", "auto"],
                "default": "auto",
                "required": False,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"1K": 6, "2K": 10, "4K": 16}, "default": "1K"},
        "enabled": True,
    },
    # ---- image-to-video (ADR 0017) — the first video category: real fields
    # confirmed via Kie's own "expected fields" panel (Grok) and a real
    # `createTask` call (Veo) rather than guessed from a simplified
    # playground Form view, same discipline as every model above. ----
    {
        "model_id": "grok-imagine-video-1-5-preview",
        "provider_model_id": "grok-imagine-video-1-5-preview",
        "fixed_inputs": {},
        "category_id": "image-to-video",
        "display_name": "Grok Imagine Video 1.5",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "image_urls",
                "label": "Reference image",
                "type": "image",
                # Kie's own schema marks this optional (the same model also
                # does pure text-to-video without it) — required here
                # instead, on purpose: this catalog row lives under
                # "Image to Video", so the category's own name should mean
                # what it says rather than silently allowing a bare
                # text-to-video call through it.
                "multiple": True,
                "max": 7,
                "required": True,
            },
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["auto", "1:1", "16:9", "9:16", "3:2", "2:3"],
                "default": "auto",
                "required": False,
            },
            {
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                # Kie's schema also allows "1080p", but the pricing banner on
                # this model's own page only ever quotes a rate for 480p/720p
                # — 1080p's real per-second rate isn't confirmed, so it's left
                # out rather than guessed (same call as GPT Image 2.5's
                # aspect-ratio/resolution constraint, ADR 0015).
                "options": ["480p", "720p"],
                "default": "480p",
                "required": False,
            },
            {
                "name": "duration",
                "label": "Duration (seconds)",
                # A genuine continuous range (unlike Veo's closed 4/6/8
                # enum, which is a `select` instead) — a `slider` (new
                # `KieInputField` type, ADR 0017, matching Kie's own
                # dashboard UI for this exact field) rather than a
                # free-text `number`: dragging a range input can't
                # physically produce an out-of-range value, where a text
                # field only describing its range in `note` never actually
                # stopped anyone from typing outside it (caught in review
                # right after the `number` version shipped).
                "type": "slider",
                "min": 1,
                "max": 15,
                "step": 1,
                "default": 8,
                "required": False,
                "note": "Range: 1-15 seconds.",
            },
            {
                "name": "nsfw_checker",
                "label": "NSFW filter",
                "type": "boolean",
                "default": True,
                "required": False,
            },
        ],
        # Per-second rate by resolution (ADR 0017's new pricing shape) — real
        # numbers from this model's own pricing banner, verified live.
        "pricing": {
            "rate_param": "duration",
            "tier_param": "resolution",
            "rates": {"480p": 2.4, "720p": 4.5},
            "default": "480p",
        },
        "enabled": True,
    },
    {
        "model_id": "veo-3-1-lite",
        # Verified with a real createTask call (2026-09-12): top-level model
        # is "veo-3-1" regardless of tier; input.model="veo3_lite" is
        # confirmed for real (Kie's own request log for a real, successful
        # 30-credit 720p job showed this exact value) — not a naming-pattern
        # guess anymore.
        #
        # The rest of this schema was corrected the same day against Kie's
        # actual published createTask body params (not the internal
        # camelCase shape their dashboard Logs page renders, which is a
        # display-layer transform, not the wire format): the real field is
        # `image_urls` (one array, 1-2 images — 1 = single reference frame,
        # 2 = first+last frame), not separate `start_frame`/`end_frame`
        # fields. `generation_type` is deliberately left unset — Kie's docs
        # say it's auto-derived from whether image_urls is given, which
        # sidesteps a real architectural gap (`fixed_inputs` can only hold
        # static values, not ones that depend on another input field).
        # `enable_fallback` is documented deprecated, left out entirely.
        "provider_model_id": "veo-3-1",
        "fixed_inputs": {"model": "veo3_lite"},
        "category_id": "image-to-video",
        "display_name": "Veo 3.1 — Lite",
        "input_schema": [
            {"name": "prompt", "label": "Prompt", "type": "text", "required": True},
            {
                "name": "image_urls",
                "label": "Start frame + optional end frame",
                "type": "image",
                "multiple": True,
                "max": 2,
                "required": True,
                "note": "Upload in order: first image is the start frame; second image (optional) is the end frame.",
            },
            {
                "name": "aspect_ratio",
                "label": "Aspect ratio",
                "type": "select",
                "options": ["16:9", "9:16", "Auto"],
                "default": "16:9",
                "required": False,
            },
            {
                "name": "resolution",
                "label": "Resolution",
                "type": "select",
                "options": ["720p", "1080p", "4k"],
                "default": "720p",
                "required": False,
            },
            {
                "name": "duration",
                "label": "Duration (seconds)",
                # A free-text `number` field let a user type an out-of-range
                # value (5, 7, 100...) that Kie's own validation would then
                # reject with no earlier feedback — unlike Grok's `duration`
                # above, which is a genuine continuous range, Kie's docs
                # enumerate exactly 3 allowed values here, so this is a
                # `select` instead. `numeric: true` (frontend, ADR 0017)
                # sends the option as a real JSON number, not its string.
                "type": "select",
                "options": ["4", "6", "8"],
                "numeric": True,
                "default": 8,
                "required": False,
            },
        ],
        "pricing": {"param": "resolution", "costs": {"720p": 30, "1080p": 35, "4k": 150}, "default": "720p"},
        # Disabled until this corrected schema is verified with one more
        # real call through our own submit_kie_job (not just Kie's own
        # website) — flipped on via PATCH /admin/kie-models/veo-3-1-lite
        # once verified, no deploy.
        "enabled": False,
    },
]


async def list_categories(db: AsyncSession, *, enabled_only: bool = True) -> list[KieCategory]:
    query = select(KieCategory)
    if enabled_only:
        query = query.where(KieCategory.enabled.is_(True))
    return list((await db.execute(query)).scalars().all())


async def list_models(
    db: AsyncSession, *, category_id: str | None = None, enabled_only: bool = True
) -> list[KieModel]:
    query = select(KieModel)
    if category_id:
        query = query.where(KieModel.category_id == category_id)
    if enabled_only:
        query = query.where(KieModel.enabled.is_(True))
    return list((await db.execute(query)).scalars().all())


async def get_model(db: AsyncSession, model_id: str) -> KieModel | None:
    return await db.get(KieModel, model_id)


async def get_category(db: AsyncSession, category_id: str) -> KieCategory | None:
    return await db.get(KieCategory, category_id)


# ---- Admin CRUD — adding/editing a model is meant to be a pure data change
# (ADR 0015), so these are plain inserts/updates against real rows, not a
# JSON-blob PATCH like capability_menu's (this table's rows are independent
# of each other, so there's no "accidentally corrupt the whole structure"
# risk that pattern exists to avoid). ----


async def create_category(db: AsyncSession, category: dict) -> KieCategory:
    if await db.get(KieCategory, category["id"]) is not None:
        raise ValueError(f"kie_category {category['id']!r} already exists")
    row = KieCategory(**category)
    db.add(row)
    return row


async def create_model(db: AsyncSession, model: dict) -> KieModel:
    if await db.get(KieModel, model["model_id"]) is not None:
        raise ValueError(f"kie_model {model['model_id']!r} already exists")
    if await db.get(KieCategory, model["category_id"]) is None:
        raise ValueError(f"unknown category_id={model['category_id']!r}")
    # ADR 0017: most models are their own provider_model_id — only Veo-style
    # split rows (several catalog entries, one real Kie model) need to pass
    # a different value explicitly.
    model = {**model, "provider_model_id": model.get("provider_model_id") or model["model_id"]}
    row = KieModel(**model)
    db.add(row)
    return row


async def update_model(db: AsyncSession, model_id: str, patch: dict) -> KieModel:
    row = await db.get(KieModel, model_id)
    if row is None:
        raise KeyError(f"no kie_model {model_id!r}")
    for key, value in patch.items():
        setattr(row, key, value)
    return row


async def delete_model(db: AsyncSession, model_id: str) -> None:
    row = await db.get(KieModel, model_id)
    if row is None:
        raise KeyError(f"no kie_model {model_id!r}")
    await db.delete(row)


def estimate_cost(kie_model: KieModel, inputs: dict[str, Any]) -> int:
    """The credit hold at submission time — an estimate curated by us
    (ADR 0015), not Kie's own number. Settlement never calls this; it uses
    Kie's `creditsConsumed` directly (services/jobs.py finalize_kie_job).

    Three pricing shapes (ADR 0015/0017): `flat` (a fixed price), a
    single-field lookup (`param`/`costs`), or a per-unit rate looked up by
    one field and multiplied by another (`rate_param`/`tier_param`/`rates`
    — e.g. credits-per-second-of-video by resolution). `math.ceil` on the
    rate shape since credits are integers (docs/data-model.md's
    conventions) but a real rate * duration is often fractional."""
    pricing = kie_model.pricing
    if "flat" in pricing:
        return pricing["flat"]
    if "rate_param" in pricing:
        tier_value = str(inputs.get(pricing["tier_param"], pricing.get("default")))
        rates = pricing["rates"]
        if tier_value not in rates:
            raise ValueError(
                f"model {kie_model.model_id!r} has no rate for "
                f"{pricing['tier_param']}={tier_value!r} (known: {sorted(rates)})"
            )
        amount = inputs.get(pricing["rate_param"])
        if amount is None:
            raise ValueError(
                f"model {kie_model.model_id!r} needs {pricing['rate_param']!r} to estimate cost"
            )
        return math.ceil(rates[tier_value] * float(amount))
    param = pricing["param"]
    value = str(inputs.get(param, pricing.get("default")))
    costs = pricing["costs"]
    if value not in costs:
        raise ValueError(
            f"model {kie_model.model_id!r} has no price for {param}={value!r} "
            f"(known: {sorted(costs)})"
        )
    return costs[value]
