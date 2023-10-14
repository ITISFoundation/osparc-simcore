import datetime
from decimal import Decimal
from typing import Any, ClassVar

from models_library.api_schemas_webserver.wallets import PaymentID
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import BaseModel, HttpUrl
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

#
# NOTE: this will be moved to the payments service
# NOTE: with https://sqlmodel.tiangolo.com/ we would only define this once!
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
