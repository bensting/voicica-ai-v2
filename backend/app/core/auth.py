"""Wraps Firebase Admin SDK token verification (ADR 0008).

Routes depend on `get_current_user`/`require_admin` here, never on
`firebase_admin` directly — so a future auth change (if this project ever
expands into a market where Firebase's reachability is a problem, see ADR
0008) is contained to this one module.
"""

import json
from dataclasses import dataclass

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import get_settings
from app.core.db import get_db
from app.services.users import get_or_create_user

_bearer_scheme = HTTPBearer(auto_error=False)


def _init_firebase() -> None:
    if firebase_admin._apps:  # already initialized (module-level singleton)
        return
    settings = get_settings()
    if settings.firebase_credentials_path:
        cred = credentials.Certificate(settings.firebase_credentials_path)
    elif settings.firebase_credentials_json:
        cred = credentials.Certificate(json.loads(settings.firebase_credentials_json))
    else:
        raise RuntimeError(
            "Firebase not configured — set FIREBASE_CREDENTIALS_PATH or "
            "FIREBASE_CREDENTIALS_JSON in .env"
        )
    firebase_admin.initialize_app(cred)


@dataclass
class CurrentUser:
    id: str
    email: str
    role: str


async def verify_identity(token: str) -> tuple[str, str]:
    """Verifies a Firebase ID token, returns (uid, email). `verify_id_token`
    is a blocking call under the hood, so it runs off the event loop."""
    _init_firebase()
    decoded = await run_in_threadpool(firebase_auth.verify_id_token, token)
    return decoded["uid"], decoded.get("email", "")


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        uid, email = await verify_identity(creds.credentials)
    except Exception as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    user = await get_or_create_user(db, uid=uid, email=email)
    return CurrentUser(id=user.id, email=user.email, role=user.role)


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role not in ("staff", "admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return user
