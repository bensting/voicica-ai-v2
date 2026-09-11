# Contributing

This is currently a single-maintainer project; these are the conventions kept so the history and docs stay usable over time — for the maintainer as much as for anyone else who reads this repo.

## Commits

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`, e.g. `feat(providers): add Azure TTS adapter`, `fix(api): validate voice id before dispatch`. Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.

## Branches

`main` is always deployable. Work happens on short-lived branches off `main` (`feat/...`, `fix/...`), merged via PR even when self-reviewed — PRs are where the diff and its rationale live side by side.

## Documenting as you go

- **Adding or changing an architectural decision** (a new pattern, a reversed choice, a new dependency that shapes the design) → add or update an ADR in [`docs/decisions/`](docs/decisions/README.md) in the same PR. See that folder's README for the process.
- **Changing module boundaries or request flow** → update [`docs/architecture.md`](docs/architecture.md) in the same PR, not as a follow-up.
- **Adding a new provider adapter** → implement it against the interface in `backend/app/providers/base.py`; if the interface itself needs to change to support it, that's an ADR (see [ADR 0001](docs/decisions/0001-provider-adapter-layer.md)).

A PR that changes structure without a matching doc update is incomplete, not just under-documented.

## Code style

Backend: Python, FastAPI, type-annotated. Formatting/linting tooling will be pinned once the backend skeleton exists (tracked as an open item — no config to follow yet).
