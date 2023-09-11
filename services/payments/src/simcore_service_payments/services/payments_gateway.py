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
import contextlib
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
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    def create(cls, settings: ApplicationSettings) -> "PaymentGatewayApi":
        client = httpx.AsyncClient(
            auth=(
                settings.PAYMENTS_GATEWAY_API_KEY.get_secret_value(),
                settings.PAYMENTS_GATEWAY_API_SECRET.get_secret_value(),
            ),
            base_url=settings.PAYMENTS_GATEWAY_URL,
        )
        exit_stack = contextlib.AsyncExitStack()

        return cls(client=client, exit_stack=exit_stack)

    async def start(self):
        await self.exit_stack.enter_async_context(self.client)

    async def close(self):
        await self.exit_stack.aclose()

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

    async def is_healhy(self) -> bool:
        try:
            await self.client.get("/health")
            return True
        except httpx.HTTPError:
            return False

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
    # app
    #

    @classmethod
    def get_from_state(cls, app: FastAPI) -> "PaymentGatewayApi":
        return app.state.payment_gateway_api  # type: ignore=[no-any-return]

    @classmethod
    def setup(cls, app: FastAPI):
        assert app.state  # nosec
        if exists := getattr(app.state, "payment_gateway_api", None):
            _logger.warning(
                "Skipping setup. Cannot setup more than once %s: %s", cls, exists
            )
            return

        assert not hasattr(app.state, "payment_gateway_api")  # nosec
        app_settings: ApplicationSettings = app.state.settings

        app.state.payment_gateway_api = api = cls.create(app_settings)

        async def on_startup():
            await api.start()

        async def on_shutdown():
            await api.close()

        app.add_event_handler("startup", on_startup)
        app.add_event_handler("shutdown", on_shutdown)


def setup_payments_gateway(app: FastAPI):
    assert app.state  # nosec
    PaymentGatewayApi.setup(app)
