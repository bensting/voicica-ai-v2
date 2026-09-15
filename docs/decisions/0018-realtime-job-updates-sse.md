# ADR 0018: Real-Time Job Completion via Redis Pub/Sub + SSE

- Status: Accepted
- Date: 2026-09-14

## Context

Every create page (TTS, voice cloning, Kie image/video) submitted, then blocked: `pollJob()` right there on the same screen, a "Generating…" button disabling the whole form until a terminal status arrived. That was always a compromise against ADR 0014's own design — submission has been genuinely async since then (`202 pending`, real background workers) — but the frontend still acted synchronous, because polling from an *ephemeral* page component only works while that component stays mounted. Navigate away, and `pollJob()`'s own docstring admits the truth: "the job itself keeps running server-side either way; this is just giving up on waiting for it in this tab."

For TTS this was mostly invisible (real providers finish in a few seconds). It stopped being invisible once Kie image/video jobs — routinely 30 seconds to several minutes, especially without a public webhook URL in local dev, where completion depends on the 1-minute poll-sweep cron rather than an instant callback — used the same pattern. The user caught this directly, on a real screenshot of a Kie image form sitting on "Generating…": *"这个等待的设计不好，因为像图片视频一般要等很久。既然我们都是异步的，我觉得所有的都要立即反馈然后再如何处理"* — since the backend is already async, the frontend should say so too: give immediate feedback, then answer "is it done yet" some other way, not by blocking the create page.

Two shapes were discussed for the "how does the user find out" half specifically:

**Plain polling from wherever the user is.** No new backend surface, but re-polling `GET /jobs` from a persistent place (the app shell, not the ephemeral create page) still means either a fixed interval (wasted requests most of the time, laggy the rest) or hand-rolled backoff — the exact trade-off ADR 0014 already accepted once for TTS/Kie's own submission responsiveness and would rather not reintroduce for "did it finish" too.

**Real-time push (this ADR).** The user asked directly whether that was worth it, and specifically whether it would also serve the still-unbuilt Android app: *"是不是上websocket/SSE一劳永逸，也更适合后续android的部分？"* Answered with what it does and doesn't actually buy: it removes polling for "did anything change" while the app is open (one persistent channel, reusable by a native Android client against the same endpoint, not a second implementation), but it doesn't replace `GET /jobs` for a page's initial state, and it doesn't reach a fully-closed app — that's a distinct, separate piece of infrastructure (FCM/APNs push), not a byproduct of choosing SSE over polling now. With that scoped correctly, real-time push was worth building.

## Decision

**Server-Sent Events, not a full WebSocket.** The channel only ever needs to go one way (server tells the client "job X finished") — SSE gets that for the cost of a plain HTTP response (`text/event-stream`), no upgrade handshake, and the browser's native `EventSource` already reconnects on its own. A full duplex channel would be solving a problem this doesn't have.

**Redis pub/sub bridges the worker process to the API process**, reusing the Redis connection ADR 0014 already put in this stack for arq — not a new external dependency. `services/jobs.py publish_job_event()` is called at every point a job actually reaches a terminal state (`_complete_success`, `_complete_kie_success`, `_complete_failure` — which alone covers every failure path across all three capabilities — plus the two spots that write a terminal state inline rather than through one of those: `execute_voice_model_training_job`'s own success branch, and `worker/cron.py sweep_stuck_jobs`'s timeout path), publishing a small `{job_id, status, capability}` payload to that job's owner's own channel (`job-events:{user_id}`). `GET /events` (`api/routes_events.py`), running in the API process, subscribes to that one channel per connected user and forwards each message as an SSE line. Best-effort throughout: a publish failure is logged, never raised — it must never affect the job's own already-committed database outcome — and `GET /jobs` stays the real source of truth regardless of whether any given event actually lands.

**Auth travels as a query param, not the `Authorization` header**, scoped to this one route: the browser's native `EventSource` can't set custom headers at all. The dependency that resolves it (`_get_current_user_from_query_token`) uses its own short-lived DB session — opened, committed, and closed before the route's actual long-running SSE generator starts — rather than `Depends(get_db)`, whose session would otherwise stay open, holding a pooled connection, for as long as the SSE connection itself does (minutes to hours).

**The frontend reconnects by hand, not via `EventSource`'s own built-in retry.** That retry would reopen the exact same URL — including the token snapshotted at connect time, stale after roughly an hour. `lib/job-events.tsx`'s `onerror` handler closes the dead connection and opens a fresh one with a newly-fetched ID token instead, so a long-lived tab keeps working past normal token expiry.

**Every create page now submits and immediately returns control** — a toast, the form usable again (values kept, not cleared, since trying a variation is a common next move), no more blocking `pollJob()` anywhere. `/app/me` (the user's own full history) is where a job's actual outcome is viewed now: every card shows its live status (a spinner while pending/processing, the real error inline if failed, the actual audio/image/video once succeeded) and live-patches in place the moment its own SSE event arrives, via `GET /jobs/{id}` for that one job — the event payload deliberately doesn't carry enough to render a result itself, keeping it a small "something changed, go re-fetch that one thing" signal rather than a second copy of `JobResponse`'s shape to keep in sync. `BottomNav`'s "Me" icon carries a small badge — how many of the user's own jobs are still in flight — seeded from a real count on load, incremented by each submission, decremented by each event, so the cue survives even navigating away from wherever a job was started.

## Alternatives considered

- **Keep polling, just move it to a persistent layer instead of the ephemeral create page.** Rejected per Context — still either a fixed interval or hand-rolled backoff, the exact cost this ADR removes for a comparable amount of engineering effort, and not reusable by Android as directly as a single HTTP endpoint both clients can subscribe to the same way.
- **A full WebSocket.** Rejected — nothing here is ever client-to-server; SSE covers the actual shape of the problem with less protocol to implement and operate (plain HTTP, works through the same infrastructure a normal request does).
- **Push the whole updated `JobResponse` through the event itself**, skipping the `GET /jobs/{id}` re-fetch on arrival. Rejected: keeps the pub/sub payload — and therefore what a worker process needs to serialize and a subscriber needs to trust — minimal; a full job body belongs to the one endpoint whose actual job is representing it correctly (auth, visibility rules, the asset-proxy shape), not duplicated into a fire-and-forget event.

## Consequences

**Positive:**
- Every capability behaves the same way now — submit, toast, done — rather than TTS feeling instant and Kie feeling stuck, which was the real complaint.
- The same `GET /events` endpoint is what a future native Android client subscribes to as well — this wasn't a web-only fix bolted onto one client.
- Reuses infrastructure already in this stack (Redis via arq) rather than adding a message broker or a second real-time system.

**Negative / open items:**
- A closed app (not just backgrounded — actually not running) still gets nothing; real "notify me even after I've left" needs FCM/APNs, a genuinely separate piece of work this ADR deliberately didn't fold in.
- `/app/me`'s media strip fetches every visible succeeded job's asset eagerly on mount (the same trade-off Explore's own thumbnail grid already made) — fine at today's history sizes, worth revisiting with lazy/viewport-based loading if a real user's history ever grows long enough for it to matter.
- Multiple open tabs each hold their own SSE connection and their own independent `pendingCount` — no cross-tab sync. Not addressed here; each tab's own badge is still correct for what that tab has seen, just not necessarily identical to another tab's.

## Related

- Builds on [ADR 0014](0014-background-job-execution.md) (the async job model this finally makes the frontend honest about) and reuses its Redis connection.
- Retires the inline "result" screens `create/tts`, `create/clone`, and `create/kie/[categoryId]/[modelId]` used to render after a blocking poll — that same audio/image/video-plus-visibility-toggle pattern now lives on `/app/me`'s own job card instead.
