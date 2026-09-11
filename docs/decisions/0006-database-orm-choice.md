# ADR 0006: Database and ORM Choice

- Status: Accepted
- Date: 2026-09-11

## Context

The data model sketched across ADR 0002 (jobs), ADR 0003 (credit ledger), and ADR 0004 (assets) needs an actual database technology. The credit ledger in particular requires strong consistency: a hold, settle, or release must never race against another operation on the same wallet and leave the balance wrong. The prior project used Postgres via Prisma — but Prisma is a Node/TypeScript-first ORM, and this rewrite's backend is FastAPI/Python, where Prisma is not the ecosystem-standard choice.

## Decision

- **Postgres**, relational — chosen specifically because the credit ledger (ADR 0003) needs transactional (ACID) guarantees around hold/settle/release; a NoSQL store would push that consistency work into application code for no benefit here.
- **SQLAlchemy 2.0 + Alembic** for the ORM/migrations (or SQLModel, which wraps SQLAlchemy with Pydantic-native models — a natural fit since FastAPI already uses Pydantic for request/response validation). Final pick between plain SQLAlchemy and SQLModel is an implementation detail, not architectural — either satisfies this ADR.
- **Neon** carried over as the hosting candidate (unchanged from the prior project) — it's standard wire-protocol Postgres, so the backend's language/ORM choice doesn't affect this pick. Still a candidate, not fully confirmed (see [README](../../README.md) tech stack table).

## Alternatives considered

- **Cloudflare D1.** Rejected: D1 is designed to be accessed from Cloudflare Workers via a binding, not as a remotely-connectable database over a standard SQL protocol. The backend is FastAPI/Python (`CLAUDE.md`'s first architecture decision), which doesn't run on Workers; using D1 would mean either moving the backend onto Workers or accessing D1 over its HTTP API from outside Cloudflare, giving up SQLAlchemy/Alembic's driver, connection-pooling, and migration tooling. D1's underlying SQLite also has a weaker write-concurrency model than Postgres's MVCC, which matters directly for the credit ledger's consistency requirements (above). R2 doesn't have this problem — it's a standard S3-compatible API reachable from anywhere, so using it (ADR 0004) alongside a non-Cloudflare-hosted backend is unrelated to this trade-off.
- **Move the whole backend onto Cloudflare Workers** (which would make D1 a natural fit). Rejected based on direct prior experience: Workers-hosted backend latency wasn't good enough when tried before. This matters more than it might otherwise, because **the core competitive bet of this rewrite is consumer-facing experience/latency** — a backend platform choice that risks that is disqualified regardless of its other merits (cost, DX, single-vendor simplicity).
- **Keep Prisma** (via its Python client). Rejected: it's a secondary, less-maintained surface of the Prisma ecosystem compared to its Node/TS client, and doesn't match how the rest of the FastAPI ecosystem is built.
- **A NoSQL document store** (e.g. Firestore, MongoDB) for everything. Rejected: the credit ledger's consistency requirements are exactly what relational databases with ACID transactions are for; modeling holds/settles as documents would mean reimplementing transactional guarantees by hand.
- **NoSQL for jobs/assets, Postgres only for credits.** Rejected as unnecessary complexity — jobs and assets have clear relational structure (foreign keys to users, one-to-one/one-to-many relationships) and no scale requirement yet that would justify splitting datastores.

## Consequences

**Positive:** one database technology for the whole backend; the credit ledger gets real transactional guarantees "for free" from Postgres; SQLAlchemy/SQLModel is the FastAPI ecosystem's default, so tooling, docs, and future hires' familiarity are all aligned.

**Negative / trade-offs:** none of the prior project's Prisma migration scripts or schema carry over — this is a fresh schema, described in [data-model.md](../data-model.md). Neon's serverless connection model (connection pooling behavior, cold starts) needs verifying once real load-testing happens — noted, not blocking.
