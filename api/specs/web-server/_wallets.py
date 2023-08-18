""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter, status
from models_library.api_schemas_webserver.wallets import (
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.generics import Envelope
from models_library.users import GroupID
from models_library.wallets import WalletID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.wallets._groups_api import WalletGroupGet
from simcore_service_webserver.wallets._groups_handlers import _WalletsGroupsBodyParams
from simcore_service_webserver.wallets._handlers import (
    _CreateWalletBodyParams,
    _PutWalletBodyParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "wallets",
    ],
)

### Wallets


@router.post(
    "/wallets",
    response_model=Envelope[WalletGet],
    status_code=201,
)
async def create_wallet(body: _CreateWalletBodyParams):
    ...


@router.get(
    "/wallets",
    response_model=Envelope[list[WalletGetWithAvailableCredits]],
)
async def list_wallets():
    ...


@router.put(
    "/wallets/{wallet_id}",
    response_model=Envelope[WalletGet],
)
async def update_wallet(wallet_id: WalletID, body: _PutWalletBodyParams):
    ...


### Wallets groups


@router.post(
    "/wallets/{wallet_id}/groups/{group_id}",
    response_model=Envelope[WalletGroupGet],
    status_code=201,
)
async def create_wallet_group(
    wallet_id: WalletID, group_id: GroupID, body: _WalletsGroupsBodyParams
):
    ...


@router.get(
    "/wallets/{wallet_id}/groups",
    response_model=Envelope[list[WalletGroupGet]],
)
async def list_wallet_groups(wallet_id: WalletID):
    ...


@router.put(
    "/wallets/{wallet_id}/groups/{group_id}",
    response_model=Envelope[WalletGroupGet],
)
async def update_wallet_group(
    wallet_id: WalletID, group_id: GroupID, body: _WalletsGroupsBodyParams
):
    ...


@router.delete(
    "/wallets/{wallet_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_wallet_group(wallet_id: WalletID, group_id: GroupID):
    ...
