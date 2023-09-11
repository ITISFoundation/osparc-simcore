import argparse
import json
import types
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from simcore_service_payments.models.payments_gateway import (
    BatchGetPaymentMethods,
    InitPayment,
    InitPaymentMethod,
    PaymentID,
    PaymentInitiated,
    PaymentMethodID,
    PaymentMethodInitiated,
    PaymentMethodsBatch,
)


def set_operation_id_as_handler_function_name(router: APIRouter):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = route.endpoint.__name__


def create_payment_router():
    router = APIRouter(
        tags=[
            "payment",
        ],
    )

    # payment
    @router.post("/init", response_model=PaymentInitiated)
    def init_payment(
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec
        assert auth  # nosec

    @router.get("/pay", response_class=HTMLResponse)
    def get_form_payment(
        id: PaymentID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec

    @router.post("/cancel")
    def cancel_payment(
        payment: PaymentInitiated,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec

    return router


def auth_session(x_init_api_secret: Annotated[str | None, Header()] = None):
    return 1


def create_payment_method_router():
    router = APIRouter(
        prefix="/payment-methods",
        tags=[
            "payment-method",
        ],
    )

    # payment-methods
    @router.post(":init", response_model=PaymentMethodInitiated)
    def init_payment_method(
        payment_method: InitPaymentMethod,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment_method  # nosec
        assert auth  # nosec

    @router.get("/form", response_class=HTMLResponse)
    def get_form_payment_method(id: PaymentMethodID):
        assert id  # nosec

    # CRUD payment-methods
    @router.post(":batchGet", response_model=PaymentMethodsBatch)
    def batch_get_payment_methods(
        batch: BatchGetPaymentMethods,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert auth  # nosec
        assert batch  # nosec

    @router.get("/{id}", response_class=HTMLResponse)
    def get_payment_method(
        id: PaymentMethodID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert auth  # nosec

    @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_payment_method(
        id: PaymentMethodID,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert id  # nosec
        assert auth  # nosec

    @router.post("/{id}:pay", response_model=PaymentInitiated)
    def pay_with_payment_method(
        id: PaymentMethodID,
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec
        assert auth  # nosec

    return router


def create_app():
    app = FastAPI(title="fake-payment-gateway")
    # TODO: create header with auth

    for factory in (
        create_payment_router,
        create_payment_method_router,
    ):
        router = factory()
        set_operation_id_as_handler_function_name(router)
        app.include_router(router)

    return app


def run_command():
    app = create_app()
    uvicorn.run(app)


def openapi_command():
    app = create_app()
    print(json.dumps(jsonable_encoder(app.openapi()), indent=1))


if __name__ == "__main__":
    # CLI: run or create schema
    parser = argparse.ArgumentParser(description="fake payment-gateway")
    subparsers = parser.add_subparsers()

    run_parser = subparsers.add_parser("run", help="Run the app")
    run_parser.set_defaults(func=run_command)

    openapi_parser = subparsers.add_parser("openapi", help="Prints openapi specs")
    run_parser.set_defaults(func=openapi_command)
