""" Interface to communicate with the payment's gateway

- httpx client with base_url to PAYMENTS_GATEWAY_URL
- Fake gateway service in services/payments/scripts/example_payment_gateway.py

"""

import contextlib
import functools
import logging
from collections.abc import Callable
from contextlib import suppress

import httpx
from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from httpx import URL, HTTPStatusError
from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID
from pydantic import TypeAdapter, ValidationError
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import (
    AttachLifespanMixin,
    BaseHTTPApi,
    HealthMixinMixin,
)
from servicelib.fastapi.httpx_utils import to_curl_command
from servicelib.fastapi.tracing import setup_httpx_client_tracing

from ..core.settings import ApplicationSettings
from ..models.payments_gateway import (
    BatchGetPaymentMethods,
    ErrorModel,
    GetPaymentMethod,
    InitPayment,
    InitPaymentMethod,
    PaymentCancelled,
    PaymentInitiated,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
)
from ..models.schemas.acknowledgements import AckPaymentWithPaymentMethod

_logger = logging.getLogger(__name__)


def _parse_raw_as_or_none(cls: type, text: str | None):
    if text:
        with suppress(ValidationError):
            return TypeAdapter(cls).validate_python(text)
    return None


class PaymentsGatewayError(OsparcErrorMixin, ValueError):
    msg_template = "{operation_id} error {status_code}: {reason}"

    @classmethod
    def from_http_status_error(
        cls, err: HTTPStatusError, operation_id: str
    ) -> "PaymentsGatewayError":
        return cls(
            operation_id=f"PaymentsGatewayApi.{operation_id}",
            reason=f"{err}",
            status_code=err.response.status_code,
            # extra context for details
            http_status_error=err,
            model=_parse_raw_as_or_none(ErrorModel, err.response.text),
        )

    def get_detailed_message(self) -> str:
        err_json = "null"
        if model := getattr(self, "model", None):
            err_json = model.model_dump_json(indent=1)

        curl_cmd = "null"
        if http_status_error := getattr(self, "http_status_error", None):
            curl_cmd = to_curl_command(http_status_error.request)

        return f"{self}\nREQ: '{curl_cmd}'\nRESP: {err_json}"


@contextlib.contextmanager
def _raise_as_payments_gateway_error(operation_id: str):
    try:
        yield

    except HTTPStatusError as err:
        error = PaymentsGatewayError.from_http_status_error(
            err, operation_id=operation_id
        )
        _logger.warning(error.get_detailed_message())
        raise error from err


def _handle_status_errors(coro: Callable):
    @functools.wraps(coro)
    async def _wrapper(self, *args, **kwargs):
        with _raise_as_payments_gateway_error(operation_id=coro.__name__):
            return await coro(self, *args, **kwargs)

    return _wrapper


class _GatewayApiAuth(httpx.Auth):
    def __init__(self, secret):
        self.token = secret

    def auth_flow(self, request):
        request.headers["X-Init-Api-Secret"] = self.token
        yield request


class PaymentsGatewayApi(
    BaseHTTPApi, AttachLifespanMixin, HealthMixinMixin, SingletonInAppStateMixin
):
    app_state_name: str = "payment_gateway_api"

    #
    # api: one-time-payment workflow
    #

    @_handle_status_errors
    async def init_payment(self, payment: InitPayment) -> PaymentInitiated:
        response = await self.client.post(
            "/init",
            json=jsonable_encoder(payment.model_dump(exclude_none=True, by_alias=True)),
        )
        response.raise_for_status()
        return PaymentInitiated.model_validate(response.json())

    def get_form_payment_url(self, id_: PaymentID) -> URL:
        return self.client.base_url.copy_with(path="/pay", params={"id": f"{id_}"})

    @_handle_status_errors
    async def cancel_payment(
        self, payment_initiated: PaymentInitiated
    ) -> PaymentCancelled:
        response = await self.client.post(
            "/cancel",
            json=jsonable_encoder(payment_initiated),
        )
        response.raise_for_status()
        return PaymentCancelled.model_validate(response.json())

    #
    # api: payment method workflows
    #

    @_handle_status_errors
    async def init_payment_method(
        self,
        payment_method: InitPaymentMethod,
    ) -> PaymentMethodInitiated:
        response = await self.client.post(
            "/payment-methods:init",
            json=jsonable_encoder(payment_method),
        )
        response.raise_for_status()
        return PaymentMethodInitiated.model_validate(response.json())

    def get_form_payment_method_url(self, id_: PaymentMethodID) -> URL:
        return self.client.base_url.copy_with(
            path="/payment-methods/form", params={"id": f"{id_}"}
        )

    # CRUD

    @_handle_status_errors
    async def get_many_payment_methods(
        self, ids_: list[PaymentMethodID]
    ) -> list[GetPaymentMethod]:
        if not ids_:
            return []
        response = await self.client.post(
            "/payment-methods:batchGet",
            json=jsonable_encoder(BatchGetPaymentMethods(payment_methods_ids=ids_)),
        )
        response.raise_for_status()
        return PaymentMethodsBatch.model_validate(response.json()).items

    @_handle_status_errors
    async def get_payment_method(self, id_: PaymentMethodID) -> GetPaymentMethod:
        response = await self.client.get(f"/payment-methods/{id_}")
        response.raise_for_status()
        return GetPaymentMethod.model_validate(response.json())

    @_handle_status_errors
    async def delete_payment_method(self, id_: PaymentMethodID) -> None:
        response = await self.client.delete(f"/payment-methods/{id_}")
        response.raise_for_status()

    @_handle_status_errors
    async def pay_with_payment_method(
        self,
        id_: PaymentMethodID,
        payment: InitPayment,
    ) -> AckPaymentWithPaymentMethod:
        response = await self.client.post(
            f"/payment-methods/{id_}:pay",
            json=jsonable_encoder(payment.model_dump(exclude_none=True, by_alias=True)),
        )
        response.raise_for_status()
        return AckPaymentWithPaymentMethod.model_validate(response.json())


def setup_payments_gateway(app: FastAPI):
    assert app.state  # nosec
    settings: ApplicationSettings = app.state.settings

    # create
    api = PaymentsGatewayApi.from_client_kwargs(
        base_url=f"{settings.PAYMENTS_GATEWAY_URL}",
        headers={"accept": "application/json"},
        auth=_GatewayApiAuth(
            secret=settings.PAYMENTS_GATEWAY_API_SECRET.get_secret_value()
        ),
    )
    if settings.PAYMENTS_TRACING:
        setup_httpx_client_tracing(api.client)
    api.attach_lifespan_to(app)
    api.set_to_app_state(app)
