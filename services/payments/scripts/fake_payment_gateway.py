import datetime
import types
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias
from uuid import UUID

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, status
from fastapi.responses import HTMLResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field


def set_operation_id_as_handler_function_name(router: APIRouter):
    for route in router.routes:
        if isinstance(route, APIRoute):
            assert isinstance(route.endpoint, types.FunctionType)  # nosec
            route.operation_id = route.endpoint.__name__


class InitPayment(BaseModel):
    amount_dollars: Decimal
    # metadata to store for billing or reference
    credits: Decimal
    user_name: str
    user_email: str
    wallet_name: str


PaymentID: TypeAlias = UUID


class PaymentInitiated(BaseModel):
    payment_id: PaymentID


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
    def get_form_payment(id: PaymentID):
        assert id  # nosec

    return router


PaymentMethodID: TypeAlias = UUID


class InitPaymentMethod(BaseModel):
    method: Literal["CC"] = "CC"
    # metadata to store for billing or reference
    user_name: str
    user_email: str
    wallet_name: str


class PaymentMethodInitiated(BaseModel):
    payment_method_id: PaymentMethodID


class GetPaymentMethod(BaseModel):
    idr: PaymentMethodID
    card_holder_name: str
    card_number_masked: str
    card_type: str
    date_created: datetime
    expiration_month: int
    expiration_year: int


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
    @router.get("", response_model=list[GetPaymentMethod])
    def list_payment_methods(
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert auth  # nosec

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
        payment: InitPayment,
        auth: Annotated[int, Depends(auth_session)],
    ):
        assert payment  # nosec
        assert auth  # nosec

    return router


class AckPayment(BaseModel):
    idr: PaymentID
    success: bool
    message: str = Field(default=None)


class AckPaymentMethod(BaseModel):
    idr: PaymentMethodID
    success: bool
    message: str = Field(default=None)


def create_payment_service_ack_routes():
    router = APIRouter(
        tags=[
            "Ack (our payment service)",
        ],
    )

    @router.post("/payments:ack", status_code=status.HTTP_200_OK)
    def ack_payment(ack: AckPayment):
        """ACK payment created by `/pay`"""
        assert ack  # nosec

    @router.post("/payments-method:ack", status_code=status.HTTP_200_OK)
    def ack_payment_method(ack: AckPaymentMethod):
        """ACK payment method added by `/paymeth-methods:init`"""
        assert ack  # nosec

    return router


def create_app():
    app = FastAPI(title="fake-payment-gateway")
    # TODO: create header with auth

    for factory in (
        create_payment_router,
        create_payment_method_router,
        create_payment_service_ack_routes,
    ):
        router = factory()
        set_operation_id_as_handler_function_name(router)
        app.include_router(router)

    return app


def main():
    app = create_app()
    uvicorn.run(app)


if __name__ == "__main__":
    # CLI: run or create schema
    main()
