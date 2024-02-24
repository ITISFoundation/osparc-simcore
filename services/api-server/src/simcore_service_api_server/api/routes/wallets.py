import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.wallets import WalletGetWithAvailableCredits
from simcore_service_api_server.models.basic_types import HTTPExceptionModel

from ..dependencies.webserver import AuthSession, get_webserver_session
from ._common import API_SERVER_DEV_FEATURES_ENABLED

_logger = logging.getLogger(__name__)

router = APIRouter()

_WALLET_RESPONSES: dict[int | str, dict[str, Any]] | None = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Returned when wallet cannot be found",
        "model": HTTPExceptionModel,
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Returned when access to wallet is not allowed",
        "model": HTTPExceptionModel,
    },
}


@router.get(
    "/default",
    response_model=WalletGetWithAvailableCredits,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    responses=_WALLET_RESPONSES,
)
async def get_default_wallet(
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_default_wallet()


@router.get(
    "/{wallet_id}",
    response_model=WalletGetWithAvailableCredits,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
    responses=_WALLET_RESPONSES,
)
async def get_wallet(
    wallet_id: int,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_wallet(wallet_id=wallet_id)
