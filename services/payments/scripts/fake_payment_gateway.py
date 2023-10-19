import argparse
import json
import types
from typing import Annotated, Any
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
from simcore_service_payments.models.schemas.auth import Token
from urllib3 import HTTPResponse

PAYMENT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Credit Card Payment</title>
</head>
<body>
    <h1>Enter Credit Card Information</h1>
    <form action="/pay?{id=}" method="POST">
        <label for="cardNumber">Credit Card Number:</label>
        <input type="text" id="cardNumber" name="cardNumber" required>
        <br><br>

        <label for="cardHolder">Name of Cardholder:</label>
        <input type="text" id="cardHolder" name="cardHolder" required>
        <br><br>

        <label for="cvs">CVS (Card Verification Value):</label>
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


def set_operation_id_as_handler_function_name(router: APIRouter):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = route.endpoint.__name__


ERROR_RESPONSES: dict[str, Any] = {"4XX": {"model": ErrorModel}}
ERROR_HTML_RESPONSES: dict[str, Any] = {
    "4XX": {"content": {"text/html": {"schema": {"type": "string"}}}}
}


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
        all_payments[payment_id] = "INITIATED"
        return PaymentInitiated(payment_id=payment_id)

    @router.get(
        "/pay",
        response_class=HTMLResponse,
        responses=ERROR_HTML_RESPONSES,
    )
    def get_payment_form(
        id: PaymentID,
    ):
        assert id  # nosec
        return HTTPResponse(PAYMENT_HTML.format(id=f"{id}"))

    @router.post(
        "/pay",
        response_class=HTMLResponse,
        responses=ERROR_HTML_RESPONSES,
        include_in_schema=False,
    )
    def pay(
        id: PaymentID,
        payment_form: Annotated[str, Form()],
        all_payments: Annotated[dict[UUID, Any], Depends(get_payments)],
    ):
        assert id  # nosec

        if all_payments[id] == "INITIATED":
            all_payments[id] = payment_form

        # request ACK
        httpx.post(
            f"http://127.0.0.1:123/v1/payments/{id}:ack",
            json={
                "success": True,
                "message": "string",
                "invoice_url": "string",
                "saved": {
                    "success": True,
                    "message": "string",
                    "payment_method_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                },
            },
            auth=PaymentsAuth(username="admin", password="adminadminadmin"),
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


def auth_session(X_Init_Api_Secret: Annotated[str | None, Header()] = None):
    # NOTE: keep `X_Init_Api_Secret` with capital letters (even if headers are case-insensitive) to
    # to agree with the specs provided by our partners

    return 1


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


def create_app():
    app = FastAPI(
        title="fake-payment-gateway",
        version="0.2.0",
        servers=[
            {
                "url": "{scheme}://{host}:{port}",
                "description": "development server",
                "variables": {
                    "scheme": {"default": "http"},
                    "host": {"default": "localhost"},
                    "port": {"default": "8080"},
                },
            }
        ],
    )

    app.state.payments = {}

    for factory in (
        create_payment_router,
        create_payment_method_router,
    ):
        router = factory()
        set_operation_id_as_handler_function_name(router)
        app.include_router(router)

    return app


def run_command(args):
    app = create_app()
    uvicorn.run(app, port=8080)


def openapi_command(args):
    app = create_app()
    print(json.dumps(jsonable_encoder(app.openapi()), indent=1))


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
