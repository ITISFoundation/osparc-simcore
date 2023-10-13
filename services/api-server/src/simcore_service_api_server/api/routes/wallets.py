import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from models_library.api_schemas_webserver.wallets import WalletGet

from ..dependencies.webserver import AuthSession, get_webserver_session
from ._common import API_SERVER_DEV_FEATURES_ENABLED

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/{wallet_id}",
    response_model=WalletGet,
    include_in_schema=API_SERVER_DEV_FEATURES_ENABLED,
)
async def get_wallet(
    wallet_id: int,
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
):
    return await webserver_api.get_wallet(wallet_id=wallet_id)
