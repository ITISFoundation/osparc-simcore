import datetime
from decimal import Decimal
from typing import Any, ClassVar

from models_library.api_schemas_webserver.wallets import (
    PaymentID,
    PaymentMethodID,
    PaymentMethodTransaction,
    PaymentTransaction,
)
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, HttpUrl
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

_EXAMPLE_AFTER_INIT = {
    "payment_id": "12345",
    "price_dollars": 10.99,
    "osparc_credits": 5.0,
    "product_name": "osparc-plus",
    "user_id": 123,
    "user_email": "user@example.com",
    "wallet_id": 123,
    "comment": "This is a test comment.",
    "invoice_url": None,
    "initiated_at": "2023-09-27T10:00:00",
    "state": PaymentTransactionState.PENDING,
}


class PaymentsTransactionsDB(BaseModel):
    payment_id: PaymentID
    price_dollars: Decimal  # accepts negatives
    osparc_credits: Decimal  # accepts negatives
    product_name: ProductName
    user_id: UserID
    user_email: LowerCaseEmailStr
    wallet_id: WalletID
    comment: str | None
    invoice_url: HttpUrl | None
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    state: PaymentTransactionState
    state_message: str | None

    class Config:
        orm_mode = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                _EXAMPLE_AFTER_INIT,
                # successful completion
                {
                    **_EXAMPLE_AFTER_INIT,
                    "invoice_url": "https://my-fake-pdf-link.com",
                    "completed_at": "2023-09-27T10:00:10",
                    "state": "SUCCESS",
                    "state_message": "Payment completed successfully",
                },
            ]
        }

    def to_api_model(self) -> PaymentTransaction:
        data: dict[str, Any] = {
            "payment_id": self.payment_id,
            "price_dollars": self.price_dollars,
            "osparc_credits": self.osparc_credits,
            "wallet_id": self.wallet_id,
            "created_at": self.initiated_at,
            "state": self.state,
            "completed_at": self.completed_at,
        }

        if self.comment:
            data["comment"] = self.comment

        if self.state_message:
            data["state_message"] = self.state_message

        if self.invoice_url:
            data["invoice_url"] = self.invoice_url

        return PaymentTransaction.parse_obj(data)


_EXAMPLE_AFTER_INIT_PAYMENT_METHOD = {
    "payment_method_id": "12345",
    "user_id": _EXAMPLE_AFTER_INIT["user_id"],
    "user_email": _EXAMPLE_AFTER_INIT["user_email"],
    "wallet_id": _EXAMPLE_AFTER_INIT["wallet_id"],
    "initiated_at": _EXAMPLE_AFTER_INIT["initiated_at"],
    "state": InitPromptAckFlowState.PENDING,
}


class PaymentsMethodsDB(BaseModel):
    payment_method_id: PaymentMethodID
    user_id: UserID
    wallet_id: WalletID
    # State in Flow
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    state: InitPromptAckFlowState
    state_message: str | None

    class Config:
        orm_mode = True
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                _EXAMPLE_AFTER_INIT_PAYMENT_METHOD,
                # successful completion
                {
                    **_EXAMPLE_AFTER_INIT_PAYMENT_METHOD,
                    "completed_at": "2023-09-27T10:00:15",
                    "state": "SUCCESS",
                    "state_message": "Payment method completed successfully",
                },
            ]
        }

    def to_api_model(self) -> PaymentMethodTransaction:
        return PaymentMethodTransaction(
            wallet_id=self.wallet_id,
            payment_method_id=self.payment_method_id,
            state=self.state.value,
        )
