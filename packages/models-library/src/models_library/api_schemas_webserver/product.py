from datetime import datetime
from typing import Annotated, TypeAlias

from pydantic import (
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PlainSerializer,
    PositiveInt,
)

from ..basic_types import IDStr, NonNegativeDecimal
from ..emails import LowerCaseEmailStr
from ..products import ProductName
from ._base import InputSchema, OutputSchema


class GetCreditPrice(OutputSchema):
    product_name: str
    usd_per_credit: Annotated[
        NonNegativeDecimal,
        PlainSerializer(float, return_type=NonNegativeFloat, when_used="json"),
    ] | None = Field(
        ...,
        description="Price of a credit in USD. "
        "If None, then this product's price is UNDEFINED",
    )
    min_payment_amount_usd: NonNegativeInt | None = Field(
        ...,
        description="Minimum amount (included) in USD that can be paid for this product"
        "Can be None if this product's price is UNDEFINED",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "productName": "osparc",
                    "usdPerCredit": None,
                    "minPaymentAmountUsd": None,
                },
                {
                    "productName": "osparc",
                    "usdPerCredit": "10",
                    "minPaymentAmountUsd": "10",
                },
            ]
        }
    )


class GetProductTemplate(OutputSchema):
    id_: IDStr = Field(..., alias="id")
    content: str


class UpdateProductTemplate(InputSchema):
    content: str


class GetProduct(OutputSchema):
    name: ProductName
    display_name: str
    short_name: str | None = Field(
        default=None, description="Short display name for SMS"
    )

    vendor: dict | None = Field(default=None, description="vendor attributes")
    issues: list[dict] | None = Field(
        default=None, description="Reference to issues tracker"
    )
    manuals: list[dict] | None = Field(default=None, description="List of manuals")
    support: list[dict] | None = Field(
        default=None, description="List of support resources"
    )

    login_settings: dict
    max_open_studies_per_user: PositiveInt | None
    is_payment_enabled: bool
    credits_per_usd: NonNegativeDecimal | None

    templates: list[GetProductTemplate] = Field(
        default_factory=list,
        description="List of templates available to this product for communications (e.g. emails, sms, etc)",
    )


ExtraCreditsUsdRangeInt: TypeAlias = Annotated[int, Field(ge=0, lt=500)]


class GenerateInvitation(InputSchema):
    guest: LowerCaseEmailStr
    trial_account_days: PositiveInt | None = None
    extra_credits_in_usd: ExtraCreditsUsdRangeInt | None = None


class InvitationGenerated(OutputSchema):
    product_name: ProductName
    issuer: str
    guest: LowerCaseEmailStr
    trial_account_days: PositiveInt | None = None
    extra_credits_in_usd: PositiveInt | None = None
    created: datetime
    invitation_link: HttpUrl

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "productName": "osparc",
                    "issuer": "john.doe",
                    "guest": "guest@example.com",
                    "trialAccountDays": 7,
                    "extraCreditsInUsd": 30,
                    "created": "2023-09-27T15:30:00",
                    "invitationLink": "https://example.com/invitation#1234",
                },
                # w/o optional
                {
                    "productName": "osparc",
                    "issuer": "john.doe@email.com",
                    "guest": "guest@example.com",
                    "created": "2023-09-27T15:30:00",
                    "invitationLink": "https://example.com/invitation#1234",
                },
            ]
        }
    )
