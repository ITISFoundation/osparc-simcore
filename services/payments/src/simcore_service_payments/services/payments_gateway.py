# - httpx client with base_url to PAYMENTS_GATEWAY_URL

# client needs to expose:
#
# one-time-payment
#   - init()
#   - execute()

# payment-method
#    - init()
#    - execute()
#    - get(), list()
#    - delete()

import httpx
from fastapi import FastAPI
from httpx import URL

from ..core.settings import ApplicationSettings
from ..models.payments_gateway import (
    GetPaymentMethod,
    InitPayment,
    InitPaymentMethod,
    PaymentID,
    PaymentInitiated,
    PaymentMethodID,
    PaymentMethodInitiated,
)

#
# payment
#


async def init_payment(payment: InitPayment, auth) -> PaymentInitiated:
    raise NotImplementedError


async def get_form_payment_url(id_: PaymentID) -> URL:
    raise NotImplementedError


#
# payment method
#


async def init_payment_method(
    payment_method: InitPaymentMethod,
    auth,
) -> PaymentMethodInitiated:
    raise NotImplementedError


async def get_form_payment_method(id_: PaymentMethodID) -> URL:
    raise NotImplementedError


async def list_payment_methods(auth) -> list[GetPaymentMethod]:
    raise NotImplementedError


async def get_payment_method(
    id_: PaymentMethodID,
    auth,
) -> GetPaymentMethod:
    raise NotImplementedError


async def delete_payment_method(id_: PaymentMethodID, auth) -> None:
    raise NotImplementedError


async def pay_with_payment_method(payment: InitPayment, auth) -> PaymentInitiated:
    raise NotImplementedError


#
# setup client
#


def setup_payments_gateway(app: FastAPI):
    assert app.state  # nosec
    app_settings: ApplicationSettings = app.state.settings

    auth = None  # TODO: add auth

    # TODO: create client
    # TODO: use base client
    app.state.payments_client = httpx.AsyncClient(
        auth=auth, base_url=app_settings.PAYMENTS_GATEWAY_URL
    )
