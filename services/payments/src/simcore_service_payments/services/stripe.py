""" Interface to communicate with the Resource Usage Tracker (RUT)

- httpx client with base_url to PAYMENTS_RESOURCE_USAGE_TRACKER

"""

import logging

import httpx
from fastapi import FastAPI
from models_library.payments import StripeInvoiceID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import (
    AttachLifespanMixin,
    BaseHTTPApi,
    HealthMixinMixin,
)

from ..core.settings import ApplicationSettings
from ..models.stripe import InvoiceData

_logger = logging.getLogger(__name__)


class _StripeBearerAuth(httpx.Auth):
    def __init__(self, token):
        self._token = token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class StripeApi(
    BaseHTTPApi, AttachLifespanMixin, HealthMixinMixin, SingletonInAppStateMixin
):
    app_state_name: str = "stripe_api"

    async def http_check_connection(
        self,
    ) -> bool:
        response = await self.client.get("/v1/products")
        response.raise_for_status()

        return True

    async def get_invoice(
        self,
        stripe_invoice_id: StripeInvoiceID,
    ) -> InvoiceData:
        response = await self.client.get(f"/v1/invoices/{stripe_invoice_id}")
        response.raise_for_status()

        return InvoiceData.parse_raw(response.text)


def setup_stripe(app: FastAPI):
    assert app.state  # nosec
    settings: ApplicationSettings = app.state.settings
    api = StripeApi.from_client_kwargs(
        base_url=settings.PAYMENTS_STRIPE_URL,
        auth=_StripeBearerAuth(settings.PAYMENTS_STRIPE_API_SECRET.get_secret_value()),
    )

    api.set_to_app_state(app)
    api.attach_lifespan_to(app)
