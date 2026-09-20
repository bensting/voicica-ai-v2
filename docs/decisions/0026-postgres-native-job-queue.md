# ADR 0026: Job Queue Moves to Postgres — SKIP LOCKED + LISTEN/NOTIFY, No More Redis/arq for Dispatch

- Status: Accepted
- Date: 2026-09-20

## Context

The Redis command-cost fix already applied to ADR 0014's queues (`WORKER_POLL_DELAY_SECONDS = 5`, ADR 0014's own Consequences) turned out insufficient once actually run continuously: five independent arq polling loops (Fish Audio/Azure/Google/Kie-submit + cron), each hitting Redis roughly every 5 seconds regardless of whether there was a job to pick up, adds up to millions of commands a month at 24/7 uptime — an order of magnitude over Upstash's free tier even after that fix, not just "helps a lot." The user asked directly: *"我们的 worker 现在是几秒轮询一次 redis，不可以有任务的时候自动触发吗？"* (can't the worker trigger only when there's a task, instead of polling every few seconds?).

Investigating arq's own source confirmed this is structural, not a missed setting: `arq.worker.Worker.main()`'s loop is a plain `asyncio.sleep()` timer (`arq/utils.py poll()`), and each iteration's `_poll_iteration()` queries Redis via `ZRANGEBYSCORE` — a sorted-set range-by-score query, needed because arq's queue supports delayed jobs, retry backoff, and cron scheduling (all "run this at time T," not "run this whenever it shows up"). A blocking primitive like `BLPOP` has no concept of "score," so it structurally can't express this — arq's polling isn't an oversight, it's the direct consequence of the delayed-job/cron feature set the project chose it for.

That reframed the real question: not "how do we make arq event-driven" (it can't be, for the same reason it's useful), but "does this job queue actually need Redis's specific semantics, given `services/jobs.py` was already written queue-mechanism-agnostic from ADR 0014 onward" — and Postgres, which this project already runs and pays for, has a genuine push primitive of its own (`LISTEN`/`NOTIFY`) that arq's Redis-based design never used.

## Decision

**The `jobs` table is the queue.** A `pending` row *is* the queue entry — no separate Redis/arq queue exists anymore. `worker/dispatcher.py` (replacing `worker/settings.py`, `worker/tasks.py`, `worker/run_all.py` entirely) claims work with:

```sql
UPDATE jobs SET status = 'processing'
WHERE id IN (
    SELECT id FROM jobs
    WHERE status = 'pending' AND (run_after IS NULL OR run_after <= now())
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT :limit
)
RETURNING id, capability, provider
```

`SELECT ... FOR UPDATE SKIP LOCKED` is the same idempotency idiom already used elsewhere in this codebase for "two things racing on one row must not double-process it" (`finalize_kie_job`, `billing.complete_purchase`, ADR 0024) — applied here to the queue's own claim step instead of a downstream settlement step. It's also what makes this safe to ever run as more than one dispatcher process later, for free, without new code.

**Woken up by a real Postgres `NOTIFY`, not a poll timer.** `services/jobs.py`'s three `submit_*` functions call `pg_queue.notify_job_ready(db)` right after committing a new `pending` row — a plain `SELECT pg_notify('jobs_ready', '')` on the caller's own (pooled) session. The dispatcher's one long-lived connection `LISTEN`s on that channel and wakes immediately. A generous fallback poll (20s) covers a missed notification (a race between commit and LISTEN registration, a brief disconnect) — the same "push primary, poll fallback" shape already used for Kie's own webhook + poll-sweep (ADR 0015), applied one level down, to the queue's own dispatch instead of a specific provider's completion tracking.

**A real, verified gotcha discovered before it could become a silent bug**: Neon's pooler connection (`DATABASE_URL`, the one this project already used everywhere) does not deliver `LISTEN`/`NOTIFY` — checked live, not assumed, with a real two-connection test:

```
POOLER connection:  received=[]        <- notification never arrives
DIRECT connection:  received=['hello'] <- arrives correctly
```

The pooler can hand a transaction a different backend connection each time, so there's no stable session for `LISTEN` to hold open. A new setting, `DATABASE_DIRECT_URL` (same host, minus `-pooler`), is required for the dispatcher's one listening connection — `DATABASE_URL` (pooled) stays exactly as it was for everything else, including the `NOTIFY` side (sending doesn't need session persistence, only receiving does).

**Per-provider concurrency moves from "separate queues" to in-process semaphores.** Reading arq's own source confirmed its `max_jobs` is implemented as a plain `asyncio.BoundedSemaphore` internally — the "give Fish Audio its own concurrency ceiling" property ADR 0014 built five separate queues to get was never actually about Redis, it was about that semaphore. `worker/dispatcher.py` keeps the exact same numbers (Fish Audio 4, Azure/Google 20, Kie-submit 10 — the same provisional caps ADR 0014 already chose) as module-level `asyncio.Semaphore`s inside one shared process, instead of five separate processes each with their own arq-managed one.

**Retry/backoff and per-job timeout, previously arq's job, are now two small columns.** `jobs.tries` (int) and `jobs.run_after` (timestamptz, nullable) replace arq's own in-memory retry counter and delayed-requeue scheduling (new migration `0013`). On `TransientProviderError`, the dispatcher sets `status` back to `pending`, increments `tries`, and sets `run_after` to a backoff delay (`5 * tries` seconds — the same constant and formula `worker/tasks.py` used) — the fallback poll (or a coincidental unrelated `NOTIFY`) picks it back up once due. `job_timeout` (300s, unchanged from ADR 0014's own reasoning) is a plain `asyncio.wait_for` around the execute call.

**Cron sweeps become plain timer loops, because they always were.** `sweep_stuck_jobs` (5 min) and `sweep_kie_processing_jobs` (1 min, ADR 0015) run inside the same dispatcher process as `asyncio.sleep(N)` loops. These were never queue-driven work — "check if 15 minutes have passed regardless of whether anything happened" has no event to `LISTEN` for — so moving off arq changes nothing about how they're scheduled, only who calls them. Their own business logic (`worker/cron.py`) is untouched.

**Redis's one remaining job is pub/sub (ADR 0018), kept deliberately, not left over.** The cost problem was 100% the polling *queue*, never the push-based SSE mechanism — `PUBLISH`/`SUBSCRIBE` volume is proportional to real activity (a publish per job completion, a subscribe per open browser tab), not a fixed per-second cost. Migrating that to Postgres `LISTEN` too was considered and rejected for this pass: `LISTEN` needs one dedicated, non-pooled connection *per listener*, so every open SSE connection would need its own direct Neon connection — Redis pub/sub doesn't have that constraint (many subscribers share cheaply). Given Neon's direct-connection ceiling is real and much lower than its pooled one, and the dispatcher's own single listener is already the one process that needs that scarce resource, doubling down on it for every open browser tab was judged the wrong trade for what it would save (an already-cheap piece of infrastructure).

## Alternatives considered

- **Increase `poll_delay` further (e.g. 30-60s) instead of restructuring anything.** Rejected as the primary fix — the math (§Context) shows this alone can't reach the free tier at real 24/7 uptime without pickup latency bad enough to notice, and it doesn't answer the user's actual question (event-driven vs. polling).
- **Consolidate the 5 arq queues into fewer arq processes, keep arq.** Considered — arq does support one `Worker` running both `functions` and `cron_jobs` together (confirmed by reading its source), so this was a real, smaller option. Rejected in favor of the fuller Postgres move once `LISTEN`/`NOTIFY` was confirmed to actually work end to end — it directly answers "trigger when there's a task" (arq's polling can't, structurally, per §Context) and removes Upstash as a dependency for anything except the already-cheap pub/sub, rather than just making the existing arq shape cheaper.
- **Move pub/sub to Postgres `LISTEN` too, drop Redis entirely.** Rejected for this pass — see Decision's last paragraph. Revisit only if Redis itself becomes a real cost/maintenance concern on its own merits; nothing here forces that.

## Consequences

**Positive:**
- The original problem (Upstash command quota) is solved at the root — the queue no longer polls Redis at all, at any interval.
- Real, measured pickup latency (job `created_at` -> `updated_at` in the database, not client-side polling overhead, which measured falsely high): ~1.3-1.7s warm, confirmed genuinely `NOTIFY`-triggered via dispatcher logs ("Woken by NOTIFY" logged immediately before every real provider call in testing) — better than the arq-era 5s `poll_delay`'s average case, not a regression traded for the cost fix.
- One fewer piece of paid infrastructure this project depends on for its most important mechanism (Redis is now pub/sub-only, a much smaller blast radius if Upstash ever has an outage).
- The "arq redelivers an already-succeeded job" failure class (ADR 0014's own documented, real, twice-observed incident) is structurally gone — `SKIP LOCKED` means a row can't be claimed again once it's no longer `pending`, by this or any future second dispatcher process, unlike arq's separate at-least-once delivery bookkeeping.

**Verified for real, not assumed correct from design alone:**
- A real TTS job: submit -> `NOTIFY` -> claim -> real Azure call -> succeeded, full round trip.
- A real Kie job: submit -> `NOTIFY` -> claim -> real `createTask` -> `processing` -> the *same* now-Redis-free `sweep_kie_processing_jobs` cron loop found it, polled Kie's real `recordInfo`, downloaded the real result, and finalized it — proving the cron-sweep half of the redesign works, not just the queue half.
- The retry/backoff path was exercised by a **real** failure, not simulated: a deliberately-garbage audio upload made Fish Audio's real API return a genuine 500 three times in a row; `jobs.tries`/`run_after` correctly incremented and rescheduled twice, then correctly wrote a final `failed` state with the real error message on the third — the exact lifecycle this ADR's retry design claims to implement, caught actually happening.
- `DATABASE_DIRECT_URL` vs. the pooler distinction: proven with a real two-connection test (§Decision) before writing a single line of dispatcher code around it, not discovered as a bug afterward.

**Negative / open items:**
- **Only ever run as one dispatcher process so far** — `SKIP LOCKED` is a well-established, standard-safe pattern for multiple concurrent claimers, but this project hasn't actually run two dispatcher processes against the same database at once to observe it. Revisit before ever actually scaling to more than one worker instance.
- **No automated tests** — same posture as the rest of this codebase (real-infrastructure verification instead, `backend/README.md`'s Conventions), but this is a meaningfully more custom piece of infrastructure (a hand-rolled claim/retry/timeout engine) than most of what this project has built so far, and a regression here is a real "jobs silently stop being processed" risk. Worth reconsidering for this specific module even if the rest of the codebase stays test-free.
- **`backend/.env.production`'s reference copy and Render's actual dashboard config both need `DATABASE_DIRECT_URL` added** before this reaches production — not done as part of this pass (this ADR covers local verification against the ADR 0025 test database only).
- **Neon's direct-connection ceiling isn't empirically known** for this account/tier — only one such connection is needed today (the dispatcher's), so not urgent, but worth checking before ever adding a second thing that wants one.
