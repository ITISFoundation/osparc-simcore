import argparse
import json
import logging
import types
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, cast
from uuid import UUID, uuid4

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
from pydantic import HttpUrl, SecretStr, parse_file_as
from servicelib.fastapi.openapi import override_fastapi_openapi_method
from settings_library.base import BaseCustomSettings
from simcore_service_payments.models.payments_gateway import (
    BatchGetPaymentMethods,
    ErrorModel,
    InitPayment,
    InitPaymentMethod,
    PaymentID,
    PaymentInitiated,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
)
from simcore_service_payments.models.schemas.acknowledgements import AckPayment
from simcore_service_payments.models.schemas.auth import Token

logging.basicConfig(level=logging.INFO)


class Settings(BaseCustomSettings):
    PAYMENTS_SERVICE_API_BASE_URL: HttpUrl
    PAYMENTS_USERNAME: str
    PAYMENTS_PASSWORD: SecretStr


def set_operation_id_as_handler_function_name(router: APIRouter):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = route.endpoint.__name__


ERROR_RESPONSES: dict[str, Any] = {"4XX": {"model": ErrorModel}}
ERROR_HTML_RESPONSES: dict[str, Any] = {
    "4XX": {"content": {"text/html": {"schema": {"type": "string"}}}}
}

PAYMENT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Credit Card Payment</title>
</head>
<body>
    <h1>Enter Credit Card Information</h1>
    <form action="/pay?id={0}" method="POST">
        <label for="cardNumber">Credit Card Number:</label>
        <input type="text" id="cardNumber" name="cardNumber" required>
        <br><br>

        <label for="cardHolder">Name of Cardholder:</label>
        <input type="text" id="cardHolder" name="cardHolder" required>
        <br><br>

        <label for="cvs">CVS:</label>
        <input type="text" id="cvs" name="cvs" required>
        <br><br>

        <label for="expirationDate">Expiration Date:</label>
        <input type="text" id="expirationDate" name="expirationDate" placeholder="MM/YY" required>
        <br><br>

        <input type="submit" value="Submit Payment">
    </form>
</body>
</html>
"""


@dataclass
class PaymentForm:
    card_number: Annotated[str, Form(alias="cardNumber")]
    card_holder: Annotated[str, Form(alias="cardHolder")]
    cvs: Annotated[str, Form()]
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


#
# Dependencies
#


def get_payments(request: Request) -> dict[str, Any]:
    return request.app.state.payments


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


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
    def init_payment(
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
        all_payments: Annotated[dict[UUID, Any], Depends(get_payments)],
    ):
        assert payment  # nosec
        assert auth  # nosec

        payment_id = uuid4()
        all_payments[payment_id] = {"init": InitPayment}

        return PaymentInitiated(payment_id=payment_id)

    @router.get(
        "/pay",
        response_class=HTMLResponse,
        responses=ERROR_HTML_RESPONSES,
    )
    def get_payment_form(
        id: PaymentID,
        all_payments: Annotated[dict[UUID, Any], Depends(get_payments)],
    ):
        assert id  # nosec

        if id not in all_payments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        return PAYMENT_HTML.format(f"{id}")

    @router.post(
        "/pay",
        response_class=HTMLResponse,
        responses=ERROR_RESPONSES,
        include_in_schema=False,
    )
    def pay(
        id: PaymentID,
        payment_form: Annotated[PaymentForm, Depends()],
        all_payments: Annotated[dict[UUID, Any], Depends(get_payments)],
        settings: Annotated[Settings, Depends(get_settings)],
    ):
        assert id  # nosec

        if id not in all_payments:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        all_payments[id]["form"] = payment_form

        # request ACK
        httpx.post(
            f"{settings.PAYMENTS_SERVICE_API_BASE_URL}/v1/payments/{id}:ack",
            json=AckPayment.Config.schema_extra["example"],  # one-time success
            auth=PaymentsAuth(
                username=settings.PAYMENTS_USERNAME,
                password=settings.PAYMENTS_PASSWORD.get_secret_value(),
            ),
        )

    @router.post(
        "/cancel",
        responses=ERROR_RESPONSES,
    )
    def cancel_payment(
        payment: PaymentInitiated,
        auth: Annotated[int, Depends(auth_session)],
        all_payments: Annotated[dict[UUID, Any], Depends(get_payments)],
    ):
        assert payment  # nosec
        assert auth  # nosec

        try:
            all_payments[payment.payment_id] = "CANCELLED"
        except KeyError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND) from exc

    return router


def auth_session(x_init_api_secret: Annotated[str | None, Header()] = None) -> int:
    return 1 if x_init_api_secret is not None else 0


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
    def init_payment_method(
        payment_method: InitPaymentMethod,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment_method  # nosec
        assert auth  # nosec

    @router.get(
        "/form",
        response_class=HTMLResponse,
        responses=ERROR_HTML_RESPONSES,
    )
    def get_form_payment_method(id: PaymentMethodID):
        assert id  # nosec

    # CRUD payment-methods
    @router.post(
        ":batchGet",
        response_model=PaymentMethodsBatch,
        responses=ERROR_RESPONSES,
    )
    def batch_get_payment_methods(
        batch: BatchGetPaymentMethods,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert auth  # nosec
        assert batch  # nosec

    @router.get(
        "/{id}",
        response_class=HTMLResponse,
        responses=ERROR_RESPONSES,
    )
    def get_payment_method(
        id: PaymentMethodID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert auth  # nosec

    @router.delete(
        "/{id}",
        status_code=status.HTTP_204_NO_CONTENT,
        responses=ERROR_RESPONSES,
    )
    def delete_payment_method(
        id: PaymentMethodID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert auth  # nosec

    @router.post(
        "/{id}:pay",
        response_model=PaymentInitiated,
        responses=ERROR_RESPONSES,
    )
    def pay_with_payment_method(
        id: PaymentMethodID,
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec
        assert auth  # nosec

    return router


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    state_path = Path("app.state.payments.ignore.json")
    if state_path.exists():
        app.state.payments = parse_file_as(dict[str, Any], state_path)

    yield

    state_path.write_text(json.dumps(jsonable_encoder(app.state.payments), indent=1))


def create_app():
    app = FastAPI(
        title="fake-payment-gateway",
        version="0.2.0",
        # servers=[
        #     {
        #         "url": "{scheme}://{host}:{port}",
        #         "description": "development server",
        #         "variables": {
        #             "scheme": {"default": "http"},
        #             "host": {"default": "localhost"},
        #             "port": {"default": "8080"},
        #         },
        #     }
        # ],
        lifespan=_app_lifespan,
        debug=True,
    )
    override_fastapi_openapi_method(app)

    app.state.payments = {}
    app.state.settings = Settings.create_from_envs()
    logging.info(app.state.settings.json(indent=2))

    for factory in (
        create_payment_router,
        create_payment_method_router,
    ):
        router = factory()
        set_operation_id_as_handler_function_name(router)
        app.include_router(router)

    return app


#
# CLI
#

the_app = create_app()


def run_command(args):
    uvicorn.run(the_app, port=8080)


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
