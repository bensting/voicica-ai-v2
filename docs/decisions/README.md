# Architecture Decision Records

An ADR captures one non-obvious technical decision: what was decided, why, and what else was considered. It exists so the reasoning survives past the chat/PR where it was made.

## When to write one

Write an ADR when a choice is hard to derive from the code alone — picking a framework, a data model shape, a pattern like the provider-adapter layer, or reversing a previous decision. Skip it for anything a reviewer could figure out by reading the diff.

## Process

1. Copy the format below into a new file: `NNNN-short-title.md`, next sequential number, lowercase-hyphenated title.
2. Set `Status: Proposed` while under discussion, `Accepted` once settled, `Superseded by ADR-XXXX` if a later ADR replaces it. Never delete or renumber an old ADR — supersede it instead, so the history stays intact.
3. Add a row to the index table below.

## Format

```markdown
# ADR NNNN: Title

- Status: Proposed | Accepted | Superseded by ADR-XXXX
- Date: YYYY-MM-DD

## Context
What problem forced this decision? What constraints mattered?

## Decision
What was decided, stated plainly.

## Alternatives considered
Other options and why they were not chosen.

## Consequences
What this makes easier, what it makes harder, what it locks in.
```

## Index

| # | Title | Status |
|---|---|---|
| [0001](0001-provider-adapter-layer.md) | Provider adapter layer for third-party voice/AI services | Accepted |
| [0002](0002-unified-async-job-model.md) | Unified async job model for all provider calls | Accepted |
| [0003](0003-credit-ledger-hold-then-settle.md) | Credit ledger with hold-then-settle lifecycle | Accepted |
| [0004](0004-asset-mirroring-r2-retention.md) | Mirror generated assets into Cloudflare R2 with a retention window | Accepted |
| [0005](0005-frontend-surfaces.md) | Frontend surfaces — one web app, separate admin, native Android | Accepted |
| [0006](0006-database-orm-choice.md) | Database and ORM choice — Postgres + SQLAlchemy/SQLModel | Accepted |
| [0007](0007-scheduled-tasks-module.md) | Scheduled/batch task module for catalog sync + stuck-job sweep | Accepted |
| [0008](0008-auth-provider.md) | Auth provider — Firebase Auth | Accepted |
| [0009](0009-voice-cloning-reusable-asset.md) | Voice cloning produces a reusable, user-owned voice asset | Accepted |
| [0010](0010-public-gallery-visibility-flag.md) | Public gallery is a visibility flag, not a separate content system | Accepted |
| [0011](0011-frontend-framework.md) | Frontend framework — Next.js | Accepted |
| [0012](0012-app-settings-table.md) | Simple tunable values live in `app_settings`, not config files | Accepted |
| [0013](0013-i18n-routing-strategy.md) | i18n routing — locale-prefixed URLs for marketing, cookie for the app | Accepted |
| [0014](0014-background-job-execution.md) | Background job execution via Redis + arq, queues split per provider | Accepted |
| [0015](0015-kie-model-catalog.md) | Kie model catalog — hand-curated DB tables, generic wire protocol | Accepted |
| [0016](0016-kie-image-to-image-uploads.md) | Kie image-to-image — short-lived public R2 uploads for reference images | Accepted |
| [0017](0017-kie-video-and-catalog-splitting.md) | Kie video category, per-unit pricing, and catalog rows outnumbering real Kie models | Accepted |
| [0018](0018-realtime-job-updates-sse.md) | Real-time job completion via Redis pub/sub + SSE, replacing inline blocking polls | Accepted |
| [0019](0019-marketing-site-scope-and-i18n.md) | Marketing site — page scope, content strategy, and i18n registration | Accepted |
| [0020](0020-admin-folded-into-web.md) | Admin folded into `frontend/web`, not a separate deployment | Accepted |
| [0021](0021-dedicated-landing-page-and-analytics.md) | Dedicated landing page (`/get`) for all future traffic, GA4 via Firebase Analytics | Accepted |
| [0022](0022-frontend-deploy-cloudflare-workers.md) | Frontend deployed to Cloudflare Workers via OpenNext | Accepted |
| [0023](0023-backend-deploy-render-singapore.md) | Backend deployed to Render, Singapore region | Accepted |
