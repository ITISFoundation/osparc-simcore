""" Interface to communicate with the payment's gateway

- httpx client with base_url to PAYMENTS_GATEWAY_URL
- Fake gateway service in services/payments/scripts/fake_payment_gateway.py

"""


import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import httpx
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
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
from ..utils.base_client_api import BaseHttpApi

_logger = logging.getLogger(__name__)


@dataclass
class PaymentsGatewayApi(BaseHttpApi):
    @classmethod
    def create(cls, settings: ApplicationSettings) -> "PaymentsGatewayApi":
        client = httpx.AsyncClient(
            auth=(
                settings.PAYMENTS_GATEWAY_API_KEY.get_secret_value(),
                settings.PAYMENTS_GATEWAY_API_SECRET.get_secret_value(),
            ),
            base_url=settings.PAYMENTS_GATEWAY_URL,
            headers={
                "X-Init-Api-Secret": settings.PAYMENTS_GATEWAY_API_SECRET.get_secret_value()
            },
        )
        exit_stack = contextlib.AsyncExitStack()

        return cls(client=client, _exit_stack=exit_stack)

    #
    # app.state
    #

    @classmethod
    def get_from_state(cls, app: FastAPI) -> "PaymentsGatewayApi":
        return cast("PaymentsGatewayApi", app.state.payment_gateway_api)

    @classmethod
    def setup_state(cls, app: FastAPI):
        # create and and save instance in state
        assert app.state  # nosec
        if exists := getattr(app.state, "payment_gateway_api", None):
            _logger.warning(
                "Skipping setup. Cannot setup more than once %s: %s", cls, exists
            )
            return

        assert not hasattr(app.state, "payment_gateway_api")  # nosec
        app_settings: ApplicationSettings = app.state.settings

        app.state.payment_gateway_api = api = cls.create(app_settings)
        assert cls.get_from_state(app) == api  # nosec

        # define lifespam
        app.add_event_handler("startup", api.start)
        app.add_event_handler("shutdown", api.close)

    #
    # api: one-time-payment workflow
    #

    async def init_payment(self, payment: InitPayment) -> PaymentInitiated:
        response = await self.client.post("/init", json=jsonable_encoder(payment))
        response.raise_for_status()
        return PaymentInitiated.parse_obj(response.json())

    def get_form_payment_url(self, id_: PaymentID) -> URL:
        return self.client.base_url.copy_with(path="/pay", params={"id": f"{id_}"})

    #
    # api: payment method workflows
    #

    async def init_payment_method(
        self,
        payment_method: InitPaymentMethod,
    ) -> PaymentMethodInitiated:
        raise NotImplementedError

    async def get_form_payment_method(self, id_: PaymentMethodID) -> URL:
        raise NotImplementedError

    async def list_payment_methods(self) -> list[GetPaymentMethod]:
        raise NotImplementedError

    async def get_payment_method(
        self,
        id_: PaymentMethodID,
    ) -> GetPaymentMethod:
        raise NotImplementedError

    async def delete_payment_method(self, id_: PaymentMethodID) -> None:
        raise NotImplementedError

    async def pay_with_payment_method(self, payment: InitPayment) -> PaymentInitiated:
        raise NotImplementedError


def setup_payments_gateway(app: FastAPI):
    assert app.state  # nosec
    PaymentsGatewayApi.setup_state(app)
