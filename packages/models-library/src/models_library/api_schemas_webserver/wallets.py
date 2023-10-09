from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar, Literal, TypeAlias

from pydantic import Field, HttpUrl, PositiveInt, validator

from ..basic_types import IDStr, NonNegativeDecimal
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
    available_credits: Decimal


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


class PaymentMethodInit(OutputSchema):
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


class PaymentMethodTransaction(OutputSchema):
    # Used ONLY in socketio interface
    wallet_id: WalletID
    payment_method_id: PaymentMethodID
    state: Literal["PENDING", "SUCCESS", "FAILED", "CANCELED"]

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "walletId": 1,
                    "paymentMethodId": "pm_0987654321",
                    "state": "SUCCESS",
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
    auto_recharge: bool = Field(
        default=False,
        description="If true, this payment-method is used for auto-recharge",
    )

    class Config(OutputSchema.Config):
        schema_extra: ClassVar[dict[str, Any]] = {
            "examples": [
                {
                    "idr": "pm_1234567890",
                    "walletId": 1,
                    "cardHolderName": "John Doe",
                    "cardNumberMasked": "**** **** **** 1234",
                    "cardType": "Visa",
                    "expirationMonth": 10,
                    "expirationYear": 2025,
                    "streetAddress": "123 Main St",
                    "zipcode": "12345",
                    "country": "United States",
                    "created": "2023-09-13T15:30:00Z",
                    "autoRecharge": "False",
                },
            ],
        }


#
# Auto-recharge mechanism associated to a wallet
#

UnlimitedLiteral: TypeAlias = Literal["UNLIMITED"]


class GetWalletAutoRecharge(OutputSchema):
    enabled: bool = Field(
        default=False,
        description="Enables/disables auto-recharge trigger in this wallet",
    )
    payment_method_id: PaymentMethodID | None = Field(
        default=None,
        description="Payment method in the wallet used to perform the auto-recharge payments",
    )
    min_balance_in_usd: NonNegativeDecimal | None = Field(
        default=None,
        description="Minimum balance in USD that triggers an auto-recharge",
    )
    inc_payment_amount_in_usd: NonNegativeDecimal | None = Field(
        default=None,
        description="Amount in USD payed when auto-recharge condition is satisfied",
    )
    inc_payment_countdown: PositiveInt | UnlimitedLiteral = Field(
        default="UNLIMITED",
        description="Maximum number of top-ups left",
    )


class ReplaceWalletAutoRecharge(InputSchema):
    enabled: bool = False
    payment_method_id: PaymentMethodID | None
    min_balance_in_usd: NonNegativeDecimal | None
    inc_payment_amount_in_usd: NonNegativeDecimal | None
    max_number_of_incs: PositiveInt | UnlimitedLiteral

    @validator("payment_method_id", "min_balance_in_usd", "inc_payment_amount_in_usd")
    @classmethod
    def validate_if_enabled(cls, v, values, field):
        if values.get("enabled") and v is None:
            msg = f"{field.name} is required when autorecharge is enabled"
            raise ValueError(msg)
