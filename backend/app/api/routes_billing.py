"""GET /billing/packages, POST /billing/checkout — one-time credit-pack
purchases via Stripe Checkout (ADR 0024). The Stripe webhook that actually
credits the wallet lives in routes_webhooks.py, alongside Kie's — same
"third-party callback target" grouping, different provider.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError
from app.core.auth import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.services import billing

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    package_key: str


class CheckoutResponse(BaseModel):
    checkout_url: str


@router.get("/packages")
async def list_packages(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await billing.list_packages(db)


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutResponse:
    base_url = get_settings().frontend_base_url

    try:
        checkout_url = await billing.create_checkout_session(
            db,
            user_id=user.id,
            package_key=body.package_key,
            success_url=f"{base_url}/app/me?purchase=success",
            cancel_url=f"{base_url}/app/me?purchase=cancelled",
        )
    except billing.UnknownPackageError as exc:
        raise APIError(status_code=400, code="unknown_package", message=str(exc)) from exc
    except billing.StripeNotConfiguredError as exc:
        raise APIError(
            status_code=503, code="billing_unavailable", message="Payments aren't configured yet."
        ) from exc

    return CheckoutResponse(checkout_url=checkout_url)
