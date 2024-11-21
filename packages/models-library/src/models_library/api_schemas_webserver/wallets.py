from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    ConfigDict,
    Field,
    HttpUrl,
    PlainSerializer,
    ValidationInfo,
    field_validator,
)

from ..basic_types import AmountDecimal, IDStr, NonNegativeDecimal
from ..users import GroupID
from ..wallets import WalletID, WalletStatus
from ._base import InputSchema, OutputSchema


class WalletGet(OutputSchema):
    wallet_id: WalletID
    name: IDStr
    description: str | None
    owner: GroupID
    thumbnail: str | None
    status: WalletStatus
    created: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True, frozen=False)


class WalletGetWithAvailableCredits(WalletGet):
    available_credits: Annotated[Decimal, PlainSerializer(float)]


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

# NOTE: that these can be UUIDs (or not)
PaymentID: TypeAlias = IDStr
PaymentMethodID: TypeAlias = IDStr


class CreateWalletPayment(InputSchema):
    price_dollars: AmountDecimal
    comment: str | None = Field(default=None, max_length=100)


class WalletPaymentInitiated(OutputSchema):
    payment_id: PaymentID
    payment_form_url: HttpUrl | None = Field(
        default=None,
        description="Link to external site that holds the payment submission form."
        "None if no prompt step is required (e.g. pre-selected credit card)",
    )


class PaymentTransaction(OutputSchema):
    payment_id: PaymentID
    price_dollars: Decimal
    wallet_id: WalletID
    osparc_credits: Decimal
    comment: str | None = Field(default=None)
    created_at: datetime
    completed_at: datetime | None
    # SEE PaymentTransactionState enum
    state: Literal["PENDING", "SUCCESS", "FAILED", "CANCELED"] = Field(
        ..., alias="completedStatus"
    )
    state_message: str | None = Field(default=None)
    invoice_url: HttpUrl | None = Field(default=None)


class PaymentMethodInitiated(OutputSchema):
    wallet_id: WalletID
    payment_method_id: PaymentMethodID
    payment_method_form_url: HttpUrl = Field(
        ..., description="Link to external site that holds the payment submission form"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "wallet_id": 1,
                    "payment_method_id": "pm_0987654321",
                    "payment_method_form_url": "https://example.com/payment-method/form",
                }
            ]
        }
    )


class PaymentMethodTransaction(OutputSchema):
    # Used ONLY in socketio interface
    wallet_id: WalletID
    payment_method_id: PaymentMethodID
    state: Literal["PENDING", "SUCCESS", "FAILED", "CANCELED"]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "walletId": 1,
                    "paymentMethodId": "pm_0987654321",
                    "state": "SUCCESS",
                }
            ]
        }
    )


class PaymentMethodGet(OutputSchema):
    idr: PaymentMethodID
    wallet_id: WalletID
    card_holder_name: str | None = None
    card_number_masked: str | None = None
    card_type: str | None = None
    expiration_month: int | None = None
    expiration_year: int | None = None
    created: datetime
    auto_recharge: bool = Field(
        default=False,
        description="If true, this payment-method is used for auto-recharge",
    )

    model_config = ConfigDict(
        frozen=False,
        json_schema_extra={
            "examples": [
                {
                    "idr": "pm_1234567890",
                    "walletId": 1,
                    "cardHolderName": "John Doe",
                    "cardNumberMasked": "**** **** **** 1234",
                    "cardType": "Visa",
                    "expirationMonth": 10,
                    "expirationYear": 2025,
                    "created": "2023-09-13T15:30:00Z",
                    "autoRecharge": "False",
                },
                {
                    "idr": "pm_1234567890",
                    "walletId": 3,
                    "created": "2024-09-13T15:30:00Z",
                    "autoRecharge": "False",
                },
            ],
        },
    )


#
# Auto-recharge mechanism associated to a wallet
#


class GetWalletAutoRecharge(OutputSchema):
    enabled: bool = Field(
        default=False,
        description="Enables/disables auto-recharge trigger in this wallet",
    )
    payment_method_id: PaymentMethodID | None = Field(
        ...,
        description="Payment method in the wallet used to perform the auto-recharge payments or None if still undefined",
    )
    min_balance_in_credits: NonNegativeDecimal = Field(
        ...,
        description="Minimum balance in credits that triggers an auto-recharge [Read only]",
    )
    top_up_amount_in_usd: NonNegativeDecimal = Field(
        ...,
        description="Amount in USD payed when auto-recharge condition is satisfied",
    )
    monthly_limit_in_usd: NonNegativeDecimal | None = Field(
        ...,
        description="Maximum amount in USD charged within a natural month."
        "None indicates no limit.",
    )


class ReplaceWalletAutoRecharge(InputSchema):
    enabled: bool
    payment_method_id: PaymentMethodID
    top_up_amount_in_usd: NonNegativeDecimal
    monthly_limit_in_usd: NonNegativeDecimal | None

    @field_validator("monthly_limit_in_usd")
    @classmethod
    def _monthly_limit_greater_than_top_up(cls, v, info: ValidationInfo):
        top_up = info.data["top_up_amount_in_usd"]
        if v is not None and v < top_up:
            msg = "Monthly limit ({v} USD) should be greater than top up amount ({top_up} USD)"
            raise ValueError(msg)
        return v
