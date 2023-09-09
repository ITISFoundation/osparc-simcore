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


import asyncio
import logging
from dataclasses import dataclass
from uuid import uuid4

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

_logger = logging.getLogger(__name__)


@dataclass
class PaymentGatewayApi:
    client: httpx.AsyncClient

    #
    # service diagnostics
    #

    async def ping(self) -> bool:
        """Check whether server is reachable"""
        try:
            await self.client.get("/")
            return True
        except httpx.RequestError:
            return False

    async def is_healhy(self):
        ...

    #
    # payment
    #

    async def init_payment(self, payment: InitPayment) -> PaymentInitiated:
        _logger.debug("FAKE: init %s", f"{payment}")
        await asyncio.sleep(2)
        return PaymentInitiated(payment_id=uuid4())

    def get_form_payment_url(self, id_: PaymentID) -> URL:
        return self.client.base_url.copy_with(path="/pay", params={"id": f"{id_}"})

    #
    # payment method
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

    #
    # setup in app
    #

    @classmethod
    def create_and_save_in_state(cls, app: FastAPI):
        assert app.state  # nosec
        assert not hasattr(app.state, "payment_gateway_api")  # nosec

        app_settings: ApplicationSettings = app.state.settings

        app.state.payment_gateway_api = cls(
            client=httpx.AsyncClient(
                auth=(
                    app_settings.PAYMENT_GATEWAY_API_KEY.get_secret_value(),
                    app_settings.PAYMENT_GATEWAY_API_SECRET.get_secret_value(),
                ),
                base_url=app_settings.PAYMENTS_GATEWAY_URL,
            )
        )

    @classmethod
    def get_from_state(cls, app: FastAPI) -> "PaymentGatewayApi":
        return app.state.payment_gateway_api


def setup_payments_gateway(app: FastAPI):
    assert app.state  # nosec
    PaymentGatewayApi.create_and_save_in_state(app)
