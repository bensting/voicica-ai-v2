# ADR 0001: Provider Adapter Layer for Third-Party Voice/AI Services

- Status: Accepted
- Date: 2026-09-11

## Context

The prior project (`voicica-ai`) called third-party voice/AI APIs (Azure, Google, Kie) directly from wherever the feature needed them — routes, services, and occasionally the frontend all held vendor-specific request/response shapes. The result:

- Adding a new vendor meant touching several unrelated places in the codebase.
- Switching a vendor for cost or quality reasons meant rewriting business logic, not just swapping a client.
- There was no single place to implement fallback (vendor A fails → try vendor B) or cost/quality-based routing — that logic would have had to be duplicated at every call site.

This rewrite is the point to fix that, before any vendor integration is (re)written.

## Decision

All third-party voice/AI providers sit behind a common abstract interface (e.g. `TTSProvider`, `VoiceCloneProvider` in `backend/app/providers/base.py`), each with one concrete adapter per vendor (`azure.py`, `google.py`, `kie.py`, ...) implementing the same method signature, e.g.:

```python
def synthesize(self, text: str, voice: str, **opts) -> AudioResult: ...
```

A `registry.py` selects the concrete provider at call time based on config and/or request parameters. `services/` and `api/` depend only on the abstract interface and the registry — never on a concrete adapter directly.

## Alternatives considered

- **Call vendor SDKs directly from services/routes.** Simplest short-term, but reproduces the exact coupling this rewrite exists to remove.
- **A single generic HTTP client with per-vendor config, no adapter classes.** Works while vendors are similar enough to share one call shape; breaks down once vendors diverge (different auth flows, streaming vs. polling, different feature sets), and was already how the prior project drifted into inconsistency.

## Consequences

**Easier:**
- Adding a vendor = one new adapter file implementing the existing interface; no changes to business logic.
- Fallback (vendor A down → vendor B) and cost/quality-based routing become logic that lives entirely in `registry.py`, implemented once.
- Each adapter is independently testable against the shared interface contract.

**Harder / trade-offs:**
- The abstract interface has to anticipate the *union* of what vendors can do; a vendor with a genuinely unique capability either forces an interface change (affects all adapters) or gets exposed as an optional/vendor-specific extension — this is a recurring design tension to watch for as more providers are added.
- One extra layer of indirection to read through compared to calling a vendor SDK inline.

## Update

The synchronous `synthesize(text, voice, **opts) -> AudioResult` signature above was illustrative. [ADR 0002](0002-unified-async-job-model.md) refines the actual interface shape to a `submit`/`poll` job model so synchronous vendors (Azure, Google) and asynchronous ones (Kie) share one contract. This ADR's core decision — one abstract interface, one adapter per vendor, a registry that selects between them — is unchanged.
