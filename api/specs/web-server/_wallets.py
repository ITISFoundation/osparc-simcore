""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from fastapi import APIRouter, status
from models_library.api_schemas_webserver.wallets import (
    CreateWalletBodyParams,
    PaymentCreateBody,
    PaymentGet,
    PutWalletBodyParams,
    WalletGet,
    WalletGetWithAvailableCredits,
)
from models_library.generics import Envelope
from models_library.rest_pagination import Page, PageQueryParameters
from models_library.users import GroupID
from models_library.wallets import WalletID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.wallets._groups_api import WalletGroupGet
from simcore_service_webserver.wallets._groups_handlers import _WalletsGroupsBodyParams

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
    status_code=status.HTTP_201_CREATED,
)
async def create_wallet(body: CreateWalletBodyParams):
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
async def update_wallet(wallet_id: WalletID, body: PutWalletBodyParams):
    ...


### Wallets payments


@router.post(
    "/wallets/{wallet_id}/payments",
    response_model=Envelope[PaymentGet],
)
async def create_payment(wallet_id: WalletID, body: PaymentCreateBody):
    """Creates payment to wallet `wallet_id`"""


@router.get(
    "/wallets/-/payments",
    response_model=Page[PaymentGet],
)
async def list_all_payments(params: PageQueryParameters):
    """Lists all user payments to his/her wallets (only the ones he/she created)"""


### Wallets groups


@router.post(
    "/wallets/{wallet_id}/groups/{group_id}",
    response_model=Envelope[WalletGroupGet],
    status_code=status.HTTP_201_CREATED,
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
