""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.wallets import (
    CreatePaymentMethodInitiated,
    CreateWalletBodyParams,
    CreateWalletPayment,
    PaymentID,
    PaymentMethodGet,
    PaymentMethodID,
    PaymentTransaction,
    PutWalletBodyParams,
    WalletGet,
    WalletGetWithAvailableCredits,
    WalletPaymentCreated,
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
    response_model=Envelope[WalletPaymentCreated],
)
async def create_payment(wallet_id: WalletID, body: CreateWalletPayment):
    """Creates payment to wallet `wallet_id`"""


@router.get(
    "/wallets/-/payments",
    response_model=Page[PaymentTransaction],
)
async def list_all_payments(params: Annotated[PageQueryParameters, Depends()]):
    """Lists all user payments to his/her wallets (only the ones he/she created)"""


@router.post(
    "/wallets/{wallet_id}/payments/{payment_id}:cancel",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_payment(wallet_id: WalletID, payment_id: PaymentID):
    ...


### Wallets payment-methods


@router.post(
    "/wallets/{wallet_id}/payments-methods:init",
    response_model=Envelope[CreatePaymentMethodInitiated],
)
async def init_creation_of_payment_method(wallet_id: WalletID):
    ...


@router.post(
    "/wallets/{wallet_id}/payments-methods/{payment_method_id}:cancel",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_creation_of_payment_method(
    wallet_id: WalletID, payment_method_id: PaymentMethodID
):
    ...


@router.get(
    "/wallets/{wallet_id}/payments-methods",
    response_model=Envelope[list[PaymentMethodGet]],
)
async def list_payments_methods(wallet_id: WalletID):
    """Lists all payments method associated to to `wallet_id`"""


@router.get(
    "/wallets/{wallet_id}/payments-methods/{payment_method_id}",
    response_model=Envelope[PaymentMethodGet],
)
async def get_payment_method(wallet_id: WalletID, payment_method_id: PaymentMethodID):
    ...


@router.delete(
    "/wallets/{wallet_id}/payments-methods/{payment_method_id}",
    response_model=Envelope[PaymentMethodGet],
)
async def delete_payment_method(
    wallet_id: WalletID, payment_method_id: PaymentMethodID
):
    ...


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
