""" Interface to communicate with the payment's gateway

- httpx client with base_url to PAYMENTS_GATEWAY_URL
- Fake gateway service in services/payments/scripts/example_payment_gateway.py

"""

import contextlib
import functools
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Coroutine

import httpx
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from httpx import URL, HTTPStatusError
from models_library.api_schemas_payments.errors import PaymentServiceUnavailableError
from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID
from pydantic import ValidationError, parse_raw_as
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import (
    AttachLifespanMixin,
    BaseHTTPApi,
    HealthMixinMixin,
)
from servicelib.fastapi.httpx_utils import to_curl_command
from simcore_service_payments.models.schemas.acknowledgements import (
    AckPaymentWithPaymentMethod,
)
from tenacity import AsyncRetrying, stop_after_delay, wait_exponential
from tenacity.retry import retry_if_exception_type
from tenacity.wait import wait_exponential

from .._constants import MSG_GATEWAY_UNAVAILABLE_ERROR, PAG
from ..core.errors import BasePaymentsGatewayError, PaymentsGatewayNotReadyError
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

_logger = logging.getLogger(__name__)


def _parse_raw_as_or_none(cls: type, text: str | None):
    if text:
        with suppress(ValidationError):
            return parse_raw_as(cls, text)
    return None


class PaymentsGatewayApiError(BasePaymentsGatewayError):
    msg_template = "{operation_id} error {status_code}: {reason}"

    @classmethod
    def from_http_status_error(
        cls, err: HTTPStatusError, operation_id: str
    ) -> "PaymentsGatewayApiError":
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
            err_json = model.json(indent=1)

        curl_cmd = "null"
        if http_status_error := getattr(self, "http_status_error", None):
            curl_cmd = to_curl_command(http_status_error.request)

        return f"{self}\nREQ: '{curl_cmd}'\nRESP: {err_json}"


@contextlib.contextmanager
def _reraise_as_service_errors_context(operation_id: str):
    try:
        yield

    except httpx.RequestError as err:
        _logger.exception("%s: request error", PAG)
        raise PaymentServiceUnavailableError(
            human_readable_detail=MSG_GATEWAY_UNAVAILABLE_ERROR
        ) from err

    except httpx.HTTPStatusError as err:
        error = PaymentsGatewayApiError.from_http_status_error(
            err, operation_id=operation_id
        )

        if err.response.is_client_error:
            _logger.warning(error.get_detailed_message())
            raise error from err

        if err.response.is_server_error:
            # 5XX in server -> turn into unavailable
            _logger.exception(error.get_detailed_message())
            raise PaymentServiceUnavailableError(
                human_readable_detail=MSG_GATEWAY_UNAVAILABLE_ERROR
            ) from err


def _handle_httpx_errors(coro: Callable):
    @functools.wraps(coro)
    async def _wrapper(self, *args, **kwargs):
        with _reraise_as_service_errors_context(operation_id=coro.__name__):
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

    @_handle_httpx_errors
    async def init_payment(self, payment: InitPayment) -> PaymentInitiated:
        response = await self.client.post(
            "/init",
            json=jsonable_encoder(payment),
        )
        response.raise_for_status()
        return PaymentInitiated.parse_obj(response.json())

    def get_form_payment_url(self, id_: PaymentID) -> URL:
        return self.client.base_url.copy_with(path="/pay", params={"id": f"{id_}"})

    @_handle_httpx_errors
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

    @_handle_httpx_errors
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

    @_handle_httpx_errors
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
        return PaymentMethodsBatch.parse_obj(response.json()).items

    @_handle_httpx_errors
    async def get_payment_method(self, id_: PaymentMethodID) -> GetPaymentMethod:
        response = await self.client.get(f"/payment-methods/{id_}")
        response.raise_for_status()
        return GetPaymentMethod.parse_obj(response.json())

    @_handle_httpx_errors
    async def delete_payment_method(self, id_: PaymentMethodID) -> None:
        response = await self.client.delete(f"/payment-methods/{id_}")
        response.raise_for_status()

    @_handle_httpx_errors
    async def pay_with_payment_method(
        self, id_: PaymentMethodID, payment: InitPayment
    ) -> AckPaymentWithPaymentMethod:
        response = await self.client.post(
            f"/payment-methods/{id_}:pay",
            json=jsonable_encoder(payment),
        )
        response.raise_for_status()
        return AckPaymentWithPaymentMethod.parse_obj(response.json())


def _create_start_policy(api: PaymentsGatewayApi) -> Callable[[], Coroutine]:
    # Start policy:
    #  - this service will not be able to start if payments-gateway is alive
    #
    async def _():
        results = []
        async for attempt in AsyncRetrying(
            wait=wait_exponential(max=3),
            stop=stop_after_delay(max_delay=6),
            retry=retry_if_exception_type(PaymentsGatewayNotReadyError),
            reraise=True,
        ):
            with attempt:
                alive = await api.check_liveness()
                results.append(alive)
                if not alive:
                    raise PaymentsGatewayNotReadyError(checks=results)

    return _


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

    app.add_event_handler("startup", _create_start_policy(api))
