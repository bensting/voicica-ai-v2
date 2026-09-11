# ADR 0002: Unified Async Job Model for All Provider Calls

- Status: Accepted
- Date: 2026-09-11

## Context

Kie's generation APIs (image, music, video) are asynchronous: submit a request, then poll or receive a webhook for the result — generation can take from seconds to minutes. Azure and Google's speech APIs (TTS, voice cloning) are synchronous: the result comes back in the same call.

If the backend exposed these as two different contracts — a synchronous response for speech, a job-and-poll flow for Kie — that split would propagate upward into `services/`, `api/`, and the frontend, each of which would need to branch on "is this capability sync or async." That is exactly the coupling [ADR 0001](0001-provider-adapter-layer.md) exists to prevent: swapping a provider for a given capability (e.g. a voice-cloning vendor that happens to be async) would then force an API-shape change.

## Decision

Every capability is exposed through one uniform contract, regardless of the underlying provider's native call shape: **submit a request → get back a Job → poll the job until it reaches a terminal state** (`succeeded` / `failed`).

- **Synchronous providers** (Azure, Google): the adapter's `submit` performs the work inline and returns a Job that is already terminal by the time the API responds. `poll` on such a job is a no-op that immediately reports the stored terminal state.
- **Asynchronous providers** (Kie): `submit` returns a Job in `pending`/`processing` state immediately; `poll` (or a webhook receiver, once confirmed available — see [product-scope.md §1.2](../product-scope.md)) advances it to a terminal state later.

`base.py` reflects this directly:

```python
def submit(self, capability: str, inputs: dict, **opts) -> ProviderJobRef: ...
def poll(self, job_ref: ProviderJobRef) -> JobStatus: ...
```

A single `jobs` table backs every capability (id, capability, provider, model_id, status, input, output, error, user_id, timestamps) — there is no separate data model per capability.

Whether the frontend *presents* a capability as instant (poll tightly until done, e.g. for a fast TTS call) or as a visible in-progress state (video generation) is a frontend/UX decision layered on top of this contract. It does not change the API or provider contract.

## Alternatives considered

- **Two contracts, chosen per capability** (sync for speech, job-based for Kie). Rejected: pushes the sync/async distinction into `services/`, `api/`, and the frontend — the coupling this architecture exists to avoid.
- **Async only for Kie, direct synchronous endpoints for Azure/Google.** Rejected for the same reason: the split follows today's accidental choice of vendors, not a real product distinction, and would need to be undone the moment a synchronous-capability vendor is replaced by an asynchronous one.

## Consequences

**Positive:**
- One job model, one `jobs` table, one status/poll endpoint shape for every capability.
- A future provider's native call shape (sync or async) is a non-event for `services/`, `api/`, and the frontend.
- One natural place to attach per-job cost/usage accounting once the billing model (product-scope.md §1.2) is decided.

**Negative / trade-offs:**
- Synchronous providers pay a small overhead — a job record is written even though the result is already known when the request returns.
- The API never offers a "pure instant response" shape; every capability, including fast ones, is technically a job lookup. Accepted as the cost of one contract across providers with genuinely different native call shapes.
- Kie's job model requires a polling mechanism (and possibly a public webhook receiver) to exist from early on, ahead of some other product decisions (billing, auth boundary) that are still open.

## Related

Refines the provider-interface shape sketched in [ADR 0001](0001-provider-adapter-layer.md) (which used a synchronous `synthesize()` example); it does not reverse ADR 0001's core decision (one abstract interface, one adapter per vendor, registry selects the provider).
