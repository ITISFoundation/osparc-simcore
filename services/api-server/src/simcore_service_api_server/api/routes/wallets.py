import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits

from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.schemas.errors import ErrorGet
from ..dependencies.webserver import AuthSession, get_webserver_session
from ._common import API_SERVER_DEV_FEATURES_ENABLED

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
} | DEFAULT_BACKEND_SERVICE_STATUS_CODES


@router.get(
    "/default",
    response_model=WalletGetWithAvailableCredits,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    responses=WALLET_STATUS_CODES,
)
async def get_default_wallet(
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_default_wallet()


@router.get(
    "/{wallet_id}",
    response_model=WalletGetWithAvailableCredits,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    responses=WALLET_STATUS_CODES,
)
async def get_wallet(
    wallet_id: int,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_wallet(wallet_id=wallet_id)
