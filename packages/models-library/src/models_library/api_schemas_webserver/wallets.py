from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Literal, TypeAlias

from pydantic import Field, HttpUrl

from ..basic_types import IDStr
from ..users import GroupID
from ..utils.pydantic_tools_extension import FieldNotRequired
from ..wallets import WalletID, WalletStatus
from ._base import InputSchema, OutputSchema


class WalletGet(OutputSchema):
    wallet_id: WalletID
    name: str
    description: str | None
    owner: GroupID
    thumbnail: str | None
    status: WalletStatus
    created: datetime
    modified: datetime


class WalletGetWithAvailableCredits(WalletGet):
    available_credits: float


class WalletGetPermissions(WalletGet):
    read: bool
    write: bool
    delete: bool


class CreateWalletBodyParams(OutputSchema):
    name: str
    description: str | None = None
    thumbnail: str | None = None


class PutWalletBodyParams(OutputSchema):
    name: str
    description: str | None
    thumbnail: str | None
    status: WalletStatus


#
# Payments to top-up credits in wallets
#

PaymentID: TypeAlias = IDStr


class CreateWalletPayment(InputSchema):
    price_dollars: Decimal
    comment: str = FieldNotRequired(max_length=100)


class WalletPaymentCreated(OutputSchema):
    payment_id: PaymentID
    payment_form_url: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )


class PaymentTransaction(OutputSchema):
    payment_id: PaymentID
    price_dollars: Decimal
    wallet_id: WalletID
    osparc_credits: Decimal
    comment: str = FieldNotRequired()
    created_at: datetime
    completed_at: datetime | None
    # SEE PaymentTransactionState enum
    state: Literal["PENDING", "SUCCESS", "FAILED", "CANCELED"] = Field(
        ..., alias="completedStatus"
    )
    state_message: str = FieldNotRequired()
    invoice_url: HttpUrl = FieldNotRequired()


PaymentMethodID: TypeAlias = IDStr


class CreatePaymentMethodInitiated(OutputSchema):
    wallet_id: WalletID
    payment_method_id: PaymentMethodID
    payment_method_form_url: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "wallet_id": 1,
                    "payment_method_id": "pm_0987654321",
                    "payment_method_form_url": "https://example.com/payment-method/form",
                }
            ]
        }


class PaymentMethodGet(OutputSchema):
    idr: PaymentMethodID
    wallet_id: WalletID
    card_holder_name: str
    card_number_masked: str
    card_type: str
    expiration_month: int
    expiration_year: int
    street_address: str
    zipcode: str
    country: str
    created: datetime

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "idr": "pm_1234567890",
                    "wallet_id": 1,
                    "card_holder_name": "John Doe",
                    "card_number_masked": "**** **** **** 1234",
                    "card_type": "Visa",
                    "expiration_month": 10,
                    "expiration_year": 2025,
                    "street_address": "123 Main St",
                    "zipcode": "12345",
                    "country": "United States",
                    "created": "2023-09-13T15:30:00Z",
                },
            ],
        }
