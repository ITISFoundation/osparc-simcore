import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.schemas.errors import ErrorGet
from ...models.schemas.model_adapter import WalletGetWithAvailableCreditsLegacy
from ..dependencies.webserver_http import AuthSession, get_webserver_session
from ._constants import FMSG_CHANGELOG_NEW_IN_VERSION

_logger = logging.getLogger(__name__)

router = APIRouter()

WALLET_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Wallet not found",
        "model": ErrorGet,
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Access to wallet is not allowed",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}


@router.get(
    "/default",
    description="Get default wallet\n\n" + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7"),
    response_model=WalletGetWithAvailableCreditsLegacy,
    responses=WALLET_STATUS_CODES,
)
async def get_default_wallet(
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_default_wallet()


@router.get(
    "/{wallet_id}",
    response_model=WalletGetWithAvailableCreditsLegacy,
    responses=WALLET_STATUS_CODES,
    description="Get wallet\n\n" + FMSG_CHANGELOG_NEW_IN_VERSION.format("0.7"),
)
async def get_wallet(
    wallet_id: int,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_wallet(wallet_id=wallet_id)
