#!/usr/bin/env python

# pylint: disable=protected-access
# pylint: disable=redefined-builtin
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

""" This is a simple example of a payments-gateway service

    - Mainly used to create the openapi specs (SEE `openapi.json`) that the payments service expects
    - Also used as a fake payment-gateway for manual exploratory testing
"""


import argparse
import datetime
import json
import logging
import types
from dataclasses import dataclass
from typing import Annotated, Any, cast
from uuid import uuid4

import httpx
import uvicorn
from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    Form,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from pydantic import HttpUrl, SecretStr
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from settings_library.base import BaseCustomSettings
from simcore_service_payments.models.payments_gateway import (
    BatchGetPaymentMethods,
    ErrorModel,
    GetPaymentMethod,
    InitPayment,
    InitPaymentMethod,
    PaymentCancelled,
    PaymentID,
    PaymentInitiated,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
)
from simcore_service_payments.models.schemas.acknowledgements import (
    AckPayment,
    AckPaymentMethod,
    AckPaymentWithPaymentMethod,
)
from simcore_service_payments.models.schemas.auth import Token

logging.basicConfig(level=logging.INFO)


# NOTE: please change every time there is a change in the specs
PAYMENTS_GATEWAY_SPECS_VERSION = "0.3.0"


class Settings(BaseCustomSettings):
    PAYMENTS_SERVICE_API_BASE_URL: HttpUrl = "http://replace-with-ack-service.io"
    PAYMENTS_USERNAME: str = "replace-with_username"
    PAYMENTS_PASSWORD: SecretStr = "replace-with-password"


def _set_operation_id_as_handler_function_name(router: APIRouter):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = route.endpoint.__name__


ERROR_RESPONSES: dict[str, Any] = {"4XX": {"model": ErrorModel}}
ERROR_HTML_RESPONSES: dict[str, Any] = {
    "4XX": {"content": {"text/html": {"schema": {"type": "string"}}}}
}

FORM_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Credit Card Payment</title>
</head>
<body>
    <h1>Enter Credit Card Information</h1>
    <form action="{0}" method="POST">
        <label for="cardNumber">Credit Card Number:</label>
        <input type="text" id="cardNumber" name="cardNumber" required>
        <br><br>

        <label for="cardHolder">Name of Cardholder:</label>
        <input type="text" id="cardHolder" name="cardHolder" required>
        <br><br>

        <label for="cvc">CVC:</label>
        <input type="text" id="cvc" name="cvc" required>
        <br><br>

        <label for="expirationDate">Expiration Date:</label>
        <input type="text" id="expirationDate" name="expirationDate" placeholder="MM/YY" required>
        <br><br>

        <input type="submit" value="{1}">
    </form>
</body>
</html>
"""

ERROR_HTTP = """
<!DOCTYPE html>
<html>
<head>
    <title>Error {0}</title>
</head>
<body>
    <h1>{0}</h1>
</body>
</html>
"""


@dataclass
class PaymentForm:
    card_number: Annotated[str, Form(alias="cardNumber")]
    card_holder: Annotated[str, Form(alias="cardHolder")]
    cvc: Annotated[str, Form()]
    expiration_date: Annotated[str, Form(alias="expirationDate")]


class PaymentsAuth(httpx.Auth):
    def __init__(self, username, password):
        self.form_data = {"username": username, "password": password}
        self.token = Token(access_token="Undefined", token_type="bearer")

    def build_request_access_token(self):
        return httpx.Request(
            "POST",
            "/v1/token",
            data=self.form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    def update_tokens(self, response):
        assert response.status_code == status.HTTP_200_OK  # nosec
        token = Token(**response.json())
        assert token.token_type == "bearer"  # nosec
        self.token = token

    def auth_flow(self, request):
        response = yield request
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            tokens_response = yield self.build_request_access_token()
            self.update_tokens(tokens_response)

            request.headers["Authorization"] = f"Bearer {self.token.access_token}"
            yield request


async def ack_payment(id_: PaymentID, acked: AckPayment, settings: Settings):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.PAYMENTS_SERVICE_API_BASE_URL}/v1/payments/{id_}:ack",
            json=acked.model_dump(),
            auth=PaymentsAuth(
                username=settings.PAYMENTS_USERNAME,
                password=settings.PAYMENTS_PASSWORD.get_secret_value(),
            ),
        )


async def ack_payment_method(
    id_: PaymentMethodID, acked: AckPaymentMethod, settings: Settings
):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.PAYMENTS_SERVICE_API_BASE_URL}/v1/payments-methods/{id_}:ack",
            json=acked.model_dump(),
            auth=PaymentsAuth(
                username=settings.PAYMENTS_USERNAME,
                password=settings.PAYMENTS_PASSWORD.get_secret_value(),
            ),
        )


#
# Dependencies
#


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def auth_session(x_init_api_secret: Annotated[str | None, Header()] = None) -> int:
    if x_init_api_secret is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="api secret missing"
        )
    return 1


#
# Router factories
#


def create_payment_router():
    router = APIRouter(
        tags=[
            "payment",
        ],
    )

    # payment
    @router.post(
        "/init",
        response_model=PaymentInitiated,
        responses=ERROR_RESPONSES,
    )
    async def init_payment(
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec
        assert auth  # nosec

        id_ = f"{uuid4()}"
        return PaymentInitiated(payment_id=id_)

    @router.get(
        "/pay",
        response_class=HTMLResponse,
        responses=ERROR_HTML_RESPONSES,
    )
    async def get_payment_form(
        id: PaymentID,
    ):
        assert id  # nosec

        return FORM_HTML.format(f"/pay?id={id}", "Submit Payment")

    @router.post(
        "/pay",
        response_class=HTMLResponse,
        responses=ERROR_RESPONSES,
        include_in_schema=False,
    )
    async def pay(
        id: PaymentID,
        payment_form: Annotated[PaymentForm, Depends()],
        settings: Annotated[Settings, Depends(get_settings)],
    ):
        """WARNING: this is only for faking pay. DO NOT EXPOSE TO openapi.json"""
        acked = AckPayment(
            success=True,
            message=f"Fake Payment {id}",
            invoice_url="https://fakeimg.pl/300/",
            saved=None,
        )
        await ack_payment(id_=id, acked=acked, settings=settings)

    @router.post(
        "/cancel",
        response_model=PaymentCancelled,
        responses=ERROR_RESPONSES,
    )
    async def cancel_payment(
        payment: PaymentInitiated,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec
        assert auth  # nosec

        return PaymentCancelled(message=f"CANCELLED {payment.payment_id}")

    return router


def create_payment_method_router():
    router = APIRouter(
        prefix="/payment-methods",
        tags=[
            "payment-method",
        ],
    )

    # payment-methods
    @router.post(
        ":init",
        response_model=PaymentMethodInitiated,
        responses=ERROR_RESPONSES,
    )
    async def init_payment_method(
        payment_method: InitPaymentMethod,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment_method  # nosec
        assert auth  # nosec

        id_ = f"{uuid4()}"
        return PaymentMethodInitiated(payment_method_id=id_)

    @router.get(
        "/form",
        response_class=HTMLResponse,
        responses=ERROR_HTML_RESPONSES,
    )
    async def get_form_payment_method(
        id: PaymentMethodID,
    ):
        return FORM_HTML.format(f"/save?id={id}", "Save Payment")

    @router.post(
        "/save",
        response_class=HTMLResponse,
        responses=ERROR_RESPONSES,
        include_in_schema=False,
    )
    async def save(
        id: PaymentMethodID,
        payment_form: Annotated[PaymentForm, Depends()],
        settings: Annotated[Settings, Depends(get_settings)],
    ):
        """WARNING: this is only for faking save. DO NOT EXPOSE TO openapi.json"""
        card_number_masked = f"**** **** **** {payment_form.card_number[-4:]}"
        acked = AckPaymentMethod(
            success=True,
            message=f"Fake Payment-method saved {card_number_masked}",
        )
        await ack_payment_method(id_=id, acked=acked, settings=settings)

    # CRUD payment-methods
    @router.post(
        ":batchGet",
        response_model=PaymentMethodsBatch,
        responses=ERROR_RESPONSES,
    )
    async def batch_get_payment_methods(
        batch: BatchGetPaymentMethods,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert auth  # nosec
        assert batch  # nosec
        return PaymentMethodsBatch(
            items=[
                GetPaymentMethod(
                    id=id_, created=datetime.datetime.now(tz=datetime.timezone.utc)
                )
                for id_ in batch.payment_methods_ids
            ]
        )

    @router.get(
        "/{id}",
        response_model=GetPaymentMethod,
        responses={
            status.HTTP_404_NOT_FOUND: {
                "model": ErrorModel,
                "description": "Payment method not found: It was not added or incomplete (i.e. create flow failed or canceled)",
            },
            **ERROR_RESPONSES,
        },
    )
    async def get_payment_method(
        id: PaymentMethodID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert auth  # nosec

        return GetPaymentMethod(
            id=id, created=datetime.datetime.now(tz=datetime.timezone.utc)
        )

    @router.delete(
        "/{id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=ERROR_RESPONSES,
    )
    async def delete_payment_method(
        id: PaymentMethodID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert auth  # nosec

    @router.post(
        "/{id}:pay",
        response_model=AckPaymentWithPaymentMethod,
        responses=ERROR_RESPONSES,
    )
    async def pay_with_payment_method(
        id: PaymentMethodID,
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert payment  # nosec
        assert auth  # nosec

        return AckPaymentWithPaymentMethod(  # nosec
            success=True,
            invoice_url="https://fakeimg.pl/300/",
            payment_id=f"{uuid4()}",
            message=f"Payed with payment-method {id}",
        )

    return router  # nosec


def create_app():
    app = FastAPI(
        title="osparc-compliant payment-gateway",
        version=PAYMENTS_GATEWAY_SPECS_VERSION,
        debug=True,
    )
    app.openapi_version = "3.0.0"  # NOTE: small hack to allow current version of `42Crunch.vscode-openapi` to work with openapi
    override_fastapi_openapi_method(app)

    app.state.settings = Settings.create_from_envs()
    logging.info(app.state.settings.model_dump_json(indent=2))

    for factory in (
        create_payment_router,
        create_payment_method_router,
    ):
        router = factory()
        _set_operation_id_as_handler_function_name(router)
        app.include_router(router)

    return app


#
# CLI
#

the_app = create_app()


def run_command(args):
    uvicorn.run(the_app, port=8000, host="0.0.0.0")  # nosec # NOSONAR


def openapi_command(args):
    print(json.dumps(jsonable_encoder(the_app.openapi()), indent=1))


if __name__ == "__main__":
    # CLI: run or create schema
    parser = argparse.ArgumentParser(description="fake payment-gateway")
    subparsers = parser.add_subparsers()

    run_parser = subparsers.add_parser("run", help="Run the app")
    run_parser.set_defaults(func=run_command)

    openapi_parser = subparsers.add_parser("openapi", help="Prints openapi specs")
    openapi_parser.set_defaults(func=openapi_command)

    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
