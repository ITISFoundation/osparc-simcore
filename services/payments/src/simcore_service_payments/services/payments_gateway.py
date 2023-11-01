""" Interface to communicate with the payment's gateway

- httpx client with base_url to PAYMENTS_GATEWAY_URL
- Fake gateway service in services/payments/scripts/fake_payment_gateway.py

"""


import logging

import httpx
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from httpx import URL
from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID

from ..core.settings import ApplicationSettings
from ..models.payments_gateway import (
    BatchGetPaymentMethods,
    GetPaymentMethod,
    InitPayment,
    InitPaymentMethod,
    PaymentCancelled,
    PaymentInitiated,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
)
from ..utils.http_client import AppStateMixin, BaseHttpApi

_logger = logging.getLogger(__name__)


class _GatewayApiAuth(httpx.Auth):
    def __init__(self, secret):
        self.token = secret

    def auth_flow(self, request):
        request.headers["X-Init-Api-Secret"] = self.token
        yield request


class PaymentsGatewayApi(BaseHttpApi, AppStateMixin):
    app_state_name: str = "payment_gateway_api"

    #
    # api: one-time-payment workflow
    #

    async def init_payment(self, payment: InitPayment) -> PaymentInitiated:
        response = await self.client.post(
            "/init",
            json=jsonable_encoder(payment),
        )
        response.raise_for_status()
        return PaymentInitiated.parse_obj(response.json())

    def get_form_payment_url(self, id_: PaymentID) -> URL:
        return self.client.base_url.copy_with(path="/pay", params={"id": f"{id_}"})

    async def cancel_payment(
        self, payment_initiated: PaymentInitiated
    ) -> PaymentCancelled:
        response = await self.client.post(
            "/cancel",
            json=jsonable_encoder(payment_initiated),
        )
        response.raise_for_status()
        return PaymentCancelled.parse_obj(response.json())

    #
    # api: payment method workflows
    #

    async def init_payment_method(
        self,
        payment_method: InitPaymentMethod,
    ) -> PaymentMethodInitiated:
        response = await self.client.post(
            "/payment-methods:init",
            json=jsonable_encoder(payment_method),
        )
        response.raise_for_status()
        return PaymentMethodInitiated.parse_obj(response.json())

    def get_form_payment_method_url(self, id_: PaymentMethodID) -> URL:
        return self.client.base_url.copy_with(
            path="/payment-methods/form", params={"id": f"{id_}"}
        )

    # CRUD

    async def get_many_payment_methods(
        self, ids_: list[PaymentMethodID]
    ) -> list[GetPaymentMethod]:
        response = await self.client.post(
            "/payment-methods:batchGet",
            json=jsonable_encoder(BatchGetPaymentMethods(payment_methods_ids=ids_)),
        )
        response.raise_for_status()
        return PaymentMethodsBatch.parse_obj(response.json()).items

    async def get_payment_method(self, id_: PaymentMethodID) -> GetPaymentMethod:
        response = await self.client.get(f"/payment-methods/{id_}")
        response.raise_for_status()
        return GetPaymentMethod.parse_obj(response.json())

    async def delete_payment_method(self, id_: PaymentMethodID) -> None:
        response = await self.client.delete(f"/payment-methods/{id_}")
        response.raise_for_status()

    async def init_payment_with_payment_method(
        self, id_: PaymentMethodID, payment: InitPayment
    ) -> PaymentInitiated:
        response = await self.client.post(
            f"/payment-methods/{id_}:pay",
            json=jsonable_encoder(payment),
        )
        response.raise_for_status()
        return PaymentInitiated.parse_obj(response.json())


def setup_payments_gateway(app: FastAPI):
    assert app.state  # nosec
    settings: ApplicationSettings = app.state.settings

    # create
    api = PaymentsGatewayApi.from_client_kwargs(
        base_url=settings.PAYMENTS_GATEWAY_URL,
        headers={"accept": "application/json"},
        auth=_GatewayApiAuth(
            secret=settings.PAYMENTS_GATEWAY_API_SECRET.get_secret_value()
        ),
    )
    api.attach_lifespan_to(app)
    api.set_to_app_state(app)
