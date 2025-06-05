from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, TypeAlias

from common_library.basic_types import DEFAULT_FACTORY
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    PlainSerializer,
    PositiveInt,
)
from pydantic.config import JsonDict

from ..basic_types import IDStr, NonNegativeDecimal
from ..emails import LowerCaseEmailStr
from ..products import ProductName
from ._base import InputSchema, OutputSchema


class CreditResultRpcGet(BaseModel):
    product_name: ProductName
    credit_amount: Decimal

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    {
                        "product_name": "s4l",
                        "credit_amount": Decimal("15.5"),  # type: ignore[dict-item]
                    },
                ]
            }
        )

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


class CreditPriceGet(OutputSchema):
    product_name: str
    usd_per_credit: Annotated[
        Annotated[
            NonNegativeDecimal,
            PlainSerializer(float, return_type=NonNegativeFloat, when_used="json"),
        ]
        | None,
        Field(
            description="Price of a credit in USD. "
            "If None, then this product's price is UNDEFINED",
        ),
    ]

    min_payment_amount_usd: Annotated[
        NonNegativeInt | None,
        Field(
            description="Minimum amount (included) in USD that can be paid for this product"
            "Can be None if this product's price is UNDEFINED",
        ),
    ]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )


class ProductTemplateGet(OutputSchema):
    id_: Annotated[IDStr, Field(alias="id")]
    content: str


class ProductGet(OutputSchema):
    name: ProductName
    display_name: str
    short_name: Annotated[
        str | None, Field(description="Short display name for SMS")
    ] = None

    vendor: Annotated[dict | None, Field(description="vendor attributes")] = None
    issues: Annotated[
        list[dict] | None, Field(description="Reference to issues tracker")
    ] = None
    manuals: Annotated[list[dict] | None, Field(description="List of manuals")] = None
    support: Annotated[
        list[dict] | None, Field(description="List of support resources")
    ] = None

    login_settings: dict
    max_open_studies_per_user: PositiveInt | None
    is_payment_enabled: bool
    credits_per_usd: NonNegativeDecimal | None

    templates: Annotated[
        list[ProductTemplateGet],
        Field(
            description="List of templates available to this product for communications (e.g. emails, sms, etc)",
            default_factory=list,
        ),
    ] = DEFAULT_FACTORY


class ProductUIGet(OutputSchema):
    product_name: ProductName
    ui: Annotated[
        dict[str, Any],
        Field(description="Front-end owned ui product configuration"),
    ]


ExtraCreditsUsdRangeInt: TypeAlias = Annotated[int, Field(ge=0, lt=500)]


TrialAccountAnnotated: TypeAlias = Annotated[
    PositiveInt | None,
    Field(
        description="Expiration time in days for trial accounts; `null` means not a trial account"
    ),
]

WelcomeCreditsAnnotated: TypeAlias = Annotated[
    ExtraCreditsUsdRangeInt | None,
    Field(description="Welcome credits in USD; `null` means no welcome credits"),
]


class InvitationGenerate(InputSchema):
    guest: LowerCaseEmailStr
    trial_account_days: TrialAccountAnnotated = None
    extra_credits_in_usd: WelcomeCreditsAnnotated = None


class InvitationGenerated(OutputSchema):
    product_name: ProductName
    issuer: str
    guest: LowerCaseEmailStr
    trial_account_days: PositiveInt | None = None
    extra_credits_in_usd: PositiveInt | None = None
    created: datetime
    invitation_link: HttpUrl

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
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

    model_config = ConfigDict(
        json_schema_extra=_update_json_schema_extra,
    )
