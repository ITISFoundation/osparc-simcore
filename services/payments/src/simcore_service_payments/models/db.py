import datetime
from decimal import Decimal
from typing import Any

from models_library.api_schemas_webserver.wallets import PaymentID, PaymentMethodID
from models_library.emails import LowerCaseEmailStr
from models_library.payments import StripeInvoiceID
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, ConfigDict, HttpUrl
from simcore_postgres_database.models.payments_methods import InitPromptAckFlowState
from simcore_postgres_database.models.payments_transactions import (
    PaymentTransactionState,
)

_EXAMPLE_AFTER_INIT: dict[str, Any] = {
    "payment_id": "12345",
    "price_dollars": 10.99,
    "osparc_credits": 5.0,
    "product_name": "osparc-plus",
    "user_id": 123,
    "user_email": "user@example.com",
    "wallet_id": 123,
    "comment": "This is a test comment.",
    "invoice_url": None,
    "stripe_invoice_id": None,
    "invoice_pdf_url": None,
    "initiated_at": "2023-09-27T10:00:00",
    "state": PaymentTransactionState.PENDING,
    "completed_at": None,
    "state_message": None,
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
    stripe_invoice_id: StripeInvoiceID | None
    invoice_pdf_url: HttpUrl | None
    initiated_at: datetime.datetime
    completed_at: datetime.datetime | None
    state: PaymentTransactionState
    state_message: str | None
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                _EXAMPLE_AFTER_INIT,
                # successful completion
                {
                    **_EXAMPLE_AFTER_INIT,
                    "invoice_url": "https://my-fake-pdf-link.com",
                    "stripe_invoice_id": "12345",
                    "invoice_pdf_url": "https://my-fake-pdf-link.com",
                    "completed_at": "2023-09-27T10:00:10",
                    "state": "SUCCESS",
                    "state_message": "Payment completed successfully",
                },
            ]
        },
    )


_EXAMPLE_AFTER_INIT_PAYMENT_METHOD = {
    "payment_method_id": "12345",
    "user_id": _EXAMPLE_AFTER_INIT["user_id"],
    "user_email": _EXAMPLE_AFTER_INIT["user_email"],
    "wallet_id": _EXAMPLE_AFTER_INIT["wallet_id"],
    "initiated_at": _EXAMPLE_AFTER_INIT["initiated_at"],
    "state": InitPromptAckFlowState.PENDING,
    "completed_at": None,
    "state_message": None,
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
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
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
        },
    )
