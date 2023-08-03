""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum

from fastapi import FastAPI, status
from models_library.api_schemas_webserver.wallets import (
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.generics import Envelope
from models_library.users import GroupID
from models_library.wallets import WalletID
from simcore_service_webserver.wallets._groups_api import WalletGroupGet
from simcore_service_webserver.wallets._groups_handlers import _WalletsGroupsBodyParams
from simcore_service_webserver.wallets._handlers import (
    _CreateWalletBodyParams,
    _PutWalletBodyParams,
)

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "wallets",
]


### Wallets


@app.post(
    "/wallets",
    response_model=Envelope[WalletGet],
    tags=TAGS,
    operation_id="create_wallet",
    status_code=201,
)
async def create_wallet(body: _CreateWalletBodyParams):
    ...


@app.get(
    "/wallets",
    response_model=Envelope[list[WalletGetWithAvailableCredits]],
    tags=TAGS,
    operation_id="list_wallets",
)
async def list_wallets():
    ...


@app.put(
    "/wallets/{wallet_id}",
    response_model=Envelope[WalletGet],
    tags=TAGS,
    operation_id="update_wallet",
)
async def update_wallet(wallet_id: WalletID, body: _PutWalletBodyParams):
    ...


### Wallets groups


@app.post(
    "/wallets/{wallet_id}/groups/{group_id}",
    response_model=Envelope[WalletGroupGet],
    tags=TAGS,
    operation_id="create_wallet_group",
    status_code=201,
)
async def create_wallet_group(
    wallet_id: WalletID, group_id: GroupID, body: _WalletsGroupsBodyParams
):
    ...


@app.get(
    "/wallets/{wallet_id}/groups",
    response_model=Envelope[list[WalletGroupGet]],
    tags=TAGS,
    operation_id="list_wallet_groups",
)
async def list_wallet_groups(wallet_id: WalletID):
    ...


@app.put(
    "/wallets/{wallet_id}/groups/{group_id}",
    response_model=Envelope[WalletGroupGet],
    tags=TAGS,
    operation_id="update_wallet_group",
)
async def update_wallet_group(
    wallet_id: WalletID, group_id: GroupID, body: _WalletsGroupsBodyParams
):
    ...


@app.delete(
    "/wallets/{wallet_id}/groups/{group_id}",
    tags=TAGS,
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_wallet_group",
)
async def delete_wallet_group(wallet_id: WalletID, group_id: GroupID):
    ...


if __name__ == "__main__":

    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-wallets.yaml")
