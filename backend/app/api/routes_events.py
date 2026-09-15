"""GET /events — real-time job-completion push (ADR 0018).

Server-Sent Events, not a full WebSocket: this channel is one-directional
(server tells the client "job X finished"), and SSE gets that for free —
plain HTTP, the browser's native `EventSource` reconnects on its own, no
custom framing needed. `services/jobs.py publish_job_event()` is the other
half: every point a job reaches a terminal state publishes to the owning
user's own Redis channel (`job-events:{user_id}`); this endpoint subscribes
to that one channel and forwards each message as an SSE event to whichever
tab is listening. Never a source of truth by itself — `GET /jobs` always
is; a missed or delayed event just costs a slightly-stale "processing" chip
until the next normal fetch, not an incorrect one.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.core.auth import CurrentUser, verify_identity
from app.core.db import async_session_factory
from app.core.queue import get_pool
from app.services.users import get_or_create_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["events"])

# How long to wait for a pub/sub message before sending a keep-alive comment
# instead — long enough to not spam idle connections, short enough that a
# proxy/load balancer's own idle-connection timeout (commonly 30-60s) never
# has a chance to silently kill this one first.
_HEARTBEAT_SECONDS = 20


async def _get_current_user_from_query_token(token: str = Query(...)) -> CurrentUser:
    """The browser's native `EventSource` can't set custom headers, so the
    Firebase ID token travels as a query param here instead of the usual
    `Authorization` header — scoped to this one route rather than weakening
    `get_current_user` globally (a query-param token is a real, if minor,
    leakage risk via proxy/access logs the header-based flow avoids).

    Uses its own short-lived DB session — opened, committed, and closed
    before the route handler's long-running SSE generator even starts —
    rather than `Depends(get_db)`, whose session would otherwise stay open
    for as long as the SSE connection itself does (minutes to hours): a
    pointless held pool connection for a route that needs the DB only to
    resolve `uid -> CurrentUser` once, not for the stream itself."""
    try:
        uid, email = await verify_identity(token)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc
    async with async_session_factory() as db:
        user = await get_or_create_user(db, uid=uid, email=email)
        await db.commit()
        return CurrentUser(id=user.id, email=user.email, role=user.role)


@router.get("/events")
async def stream_job_events(
    request: Request, user: CurrentUser = Depends(_get_current_user_from_query_token)
) -> StreamingResponse:
    async def event_stream():
        pool = await get_pool()
        pubsub = pool.pubsub()
        channel = f"job-events:{user.id}"
        await pubsub.subscribe(channel)
        logger.info("SSE: user %s subscribed to %s", user.id, channel)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=_HEARTBEAT_SECONDS
                    )
                except asyncio.CancelledError:
                    break
                if message is None:
                    yield ": keep-alive\n\n"
                    continue
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"data: {data}\n\n"
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.info("SSE: user %s unsubscribed from %s", user.id, channel)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # Disables response buffering on nginx-style reverse proxies —
            # without this, an SSE stream can sit invisibly buffered rather
            # than reaching the client as it's written.
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
