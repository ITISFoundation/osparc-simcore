""" Interface to communicate with the Resource Usage Tracker (RUT)

- httpx client with base_url to PAYMENTS_RESOURCE_USAGE_TRACKER

"""

import contextlib
import functools
import logging
from collections.abc import Callable

import httpx
from fastapi import FastAPI
from httpx import HTTPStatusError
from models_library.payments import StripeInvoiceID
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import (
    AttachLifespanMixin,
    BaseHTTPApi,
    HealthMixinMixin,
)
from servicelib.fastapi.tracing import setup_httpx_client_tracing

from ..core.errors import StripeRuntimeError
from ..core.settings import ApplicationSettings
from ..models.stripe import InvoiceData

_logger = logging.getLogger(__name__)


@contextlib.contextmanager
def _raise_as_stripe_error():
    """https://docs.stripe.com/api/errors"""
    try:
        yield

    except HTTPStatusError as err:
        raise StripeRuntimeError from err


def _handle_status_errors(coro: Callable):
    @functools.wraps(coro)
    async def _wrapper(self, *args, **kwargs):
        with _raise_as_stripe_error():
            return await coro(self, *args, **kwargs)

    return _wrapper


class _StripeBearerAuth(httpx.Auth):
    def __init__(self, token):
        self._token = token

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self._token}"
        yield request


class StripeApi(
    BaseHTTPApi, AttachLifespanMixin, HealthMixinMixin, SingletonInAppStateMixin
):
    """https://docs.stripe.com/api"""

    app_state_name: str = "stripe_api"

    async def is_healthy(
        self,
    ) -> bool:
        try:
            response = await self.client.get("/v1/products")
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    @_handle_status_errors
    async def get_invoice(
        self,
        stripe_invoice_id: StripeInvoiceID,
    ) -> InvoiceData:

        response = await self.client.get(f"/v1/invoices/{stripe_invoice_id}")
        response.raise_for_status()

        return InvoiceData.model_validate_json(response.text)


def setup_stripe(app: FastAPI):
    assert app.state  # nosec
    settings: ApplicationSettings = app.state.settings
    api = StripeApi.from_client_kwargs(
        base_url=f"{settings.PAYMENTS_STRIPE_URL}",
        auth=_StripeBearerAuth(settings.PAYMENTS_STRIPE_API_SECRET.get_secret_value()),
    )
    if settings.PAYMENTS_TRACING:
        setup_httpx_client_tracing(api.client)

    api.set_to_app_state(app)
    api.attach_lifespan_to(app)
