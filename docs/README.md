# Documentation Index

This folder is the single source of truth for how the system is designed and why. Keep it small and structured — one document per concern, updated alongside the code it describes, rather than a growing pile of one-off write-ups.

| Document | Purpose |
|---|---|
| [product-scope.md](product-scope.md) | What the platform does and for whom — capability matrix, frontend surfaces. Upstream of everything else below. |
| [architecture.md](architecture.md) | System design: diagrams, module boundaries, request flow |
| [data-model.md](data-model.md) | The authoritative database schema — ER diagram, table-by-table notes |
| [api-contract.md](api-contract.md) | The backend's HTTP surface — every endpoint, auth, conventions |
| [flows.md](flows.md) | Checklist of every operational flow in the system and how defined it is |
| [decisions/](decisions/README.md) | ADRs — the reasoning behind each non-obvious technical choice |

Read order for a newcomer: `product-scope.md` → `architecture.md` → `data-model.md` → `api-contract.md` → `flows.md` → `decisions/`.

## Rules for this folder

1. **An architecture-level decision gets an ADR before or alongside the code that implements it** — not written up after the fact, and never left only in chat history or commit messages. See [decisions/README.md](decisions/README.md).
2. **`architecture.md` is kept in sync with the code.** If a structural change lands without a matching doc update, the doc update is part of the same PR/commit, not a follow-up.
3. **Prefer diagrams over prose** for anything describing structure or flow (Mermaid renders natively on GitHub — no extra tooling needed).
4. **New file only when a topic outgrows its section** — don't pre-create empty placeholder docs for things that don't exist yet.
