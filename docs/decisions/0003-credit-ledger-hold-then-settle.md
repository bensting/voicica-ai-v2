# ADR 0003: Credit Ledger with Hold-Then-Settle Lifecycle

- Status: Accepted
- Date: 2026-09-11

## Context

Users top up a credit balance; each call's cost is not flat. It's computed from capability/model-specific parameters — e.g. text length for TTS/voice cloning, duration and resolution for a Kie video model — and will vary per Kie model as more are added.

Per [ADR 0002](0002-unified-async-job-model.md), a job can be `processing` for minutes (video generation). A naive "debit after success" design reserves nothing while jobs are in flight, so a user could submit far more concurrent jobs than their balance could ever cover. Kie does not charge for failed generations — including content/keyword rejections, not just system errors — so the credit model should guarantee the same for the user: a failed job costs nothing.

## Decision

**Cost is computed by a pricing rule** — config/data keyed by capability and, for Kie, by `model_id` — expressed as a function over the request's specific inputs (`credits = f(char_count)` for TTS, `credits = f(duration, resolution)` for a given Kie video model). This lives alongside the Kie model catalog config ([product-scope.md §1.1](../product-scope.md)) rather than being hardcoded per capability, since which parameters are billable differs per model and grows as models are added.

**Credits move through a hold → settle/release lifecycle**, tied to the job state machine from ADR 0002:

1. **Submit**: compute `estimated_cost` from the pricing rule and the request's inputs. If `balance - sum(active holds) < estimated_cost`, reject the request before it reaches any provider. Otherwise, create a hold for `estimated_cost` linked to the job, then proceed.
2. **Terminal: succeeded**: compute `actual_cost` from the same pricing rule applied to the job's actual output parameters (relevant only if a provider's delivered output can diverge from what was requested). Debit `actual_cost` from the balance and release the remainder of the hold.
3. **Terminal: failed**: release the entire hold. No debit — for any provider, not only Kie, so the guarantee is uniform across the system rather than a Kie-specific special case.

The `jobs` table (ADR 0002) gains `estimated_cost`, `actual_cost` (nullable until settlement), and a reference to its hold.

## Alternatives considered

- **Debit only after success, no hold at submit time.** Rejected: nothing is reserved while jobs are in flight, so concurrent long-running jobs can oversubscribe a balance beyond what it could ever cover.
- **Debit the full amount at submit time, refund on failure.** Rejected in favor of the hold model: a hold that only ever resolves to "released" or "settled" is a simpler ledger to reason about than one with a separate refund transaction type, and it matches vendors like Kie that never charge for failures in the first place — there is never a "money that was taken and must be given back."

## Consequences

**Positive:**
- A user is never charged for a failed job, matching Kie's own billing behavior and applied uniformly to every provider.
- Concurrent in-flight jobs can't oversubscribe a balance — available balance already reflects outstanding holds.
- Adding a new Kie model requires only adding its pricing rule as config, the same motion as adding its catalog entry (ADR 0001 update / product-scope.md §1.1).

**Negative / open items:**
- The actual credit numbers per capability/model are not decided here — they are config to fill in as each capability is implemented.
- ~~Whether a provider's actual output can diverge from its requested parameters...~~ **Resolved for Kie**: Kie's task-status response includes `creditsConsumed`, its own reported cost for the task, once terminal (see [architecture.md §3d](../architecture.md)). Settlement for Kie can derive `actual_cost` from that figure directly instead of re-deriving it from request parameters. Still open for Azure/Google, where no equivalent reported-cost field is confirmed yet — assume `actual_cost == estimated_cost` there until checked.
- Top-up (payment provider integration) is out of scope for this ADR — a future decision once a payment provider is chosen (tracked in [product-scope.md](../product-scope.md)).
