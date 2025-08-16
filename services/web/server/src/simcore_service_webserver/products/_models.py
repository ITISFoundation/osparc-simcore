import logging
import re
import string
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, Any

from models_library.basic_regex import (
    PUBLIC_VARIABLE_NAME_RE,
    TWILIO_ALPHANUMERIC_SENDER_ID_RE,
)
from models_library.basic_types import NonNegativeDecimal
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName, StripePriceID, StripeTaxRateID
from models_library.utils.change_case import snake_to_camel
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PositiveInt,
    field_serializer,
    field_validator,
)
from pydantic.config import JsonDict
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
    ProductLoginSettingsDict,
    Vendor,
    WebFeedback,
    products,
)

from ..constants import FRONTEND_APPS_AVAILABLE

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreditResult:
    product_name: ProductName
    credit_amount: Decimal


@dataclass(frozen=True)
class ProductStripeInfo:
    stripe_price_id: StripePriceID
    stripe_tax_rate_id: StripeTaxRateID


@dataclass(frozen=True)
class PaymentFields:
    enabled: bool
    credits_per_usd: Decimal | None
    min_payment_amount_usd: Decimal | None


class Product(BaseModel):
    """Model used to parse a row of pg product's table

    The info in this model is static and read-only

    SEE descriptions in packages/postgres-database/src/simcore_postgres_database/models/products.py
    """

    name: Annotated[
        ProductName,
        Field(pattern=PUBLIC_VARIABLE_NAME_RE, validate_default=True),
    ]

    display_name: Annotated[str, Field(..., description="Long display name")]
    short_name: Annotated[
        str | None,
        Field(
            None,
            pattern=re.compile(TWILIO_ALPHANUMERIC_SENDER_ID_RE),
            min_length=2,
            max_length=11,
            description="Short display name for SMS",
        ),
    ]

    host_regex: Annotated[
        re.Pattern, BeforeValidator(str.strip), Field(..., description="Host regex")
    ]

    support_email: Annotated[
        LowerCaseEmailStr,
        Field(
            description="Main support email."
            " Other support emails can be defined under 'support' field",
        ),
    ]

    product_owners_email: Annotated[
        LowerCaseEmailStr | None,
        Field(description="Used e.g. for account requests forms"),
    ] = None

    twilio_messaging_sid: Annotated[
        str | None,
        Field(min_length=34, max_length=34, description="Identifier for SMS"),
    ] = None

    vendor: Annotated[
        Vendor | None,
        Field(
            description="Vendor information such as company name, address, copyright, ...",
        ),
    ] = None

    issues: list[IssueTracker] | None = None

    manuals: list[Manual] | None = None

    support: list[Forum | EmailFeedback | WebFeedback] | None = Field(None)

    login_settings: Annotated[
        ProductLoginSettingsDict,
        Field(
            description="Product customization of login settings. "
            "Note that these are NOT the final plugin settings but those are obtained from login.settings.get_plugin_settings",
        ),
    ]

    registration_email_template: Annotated[
        str | None, Field(json_schema_extra={"x_template_name": "registration_email"})
    ] = None

    max_open_studies_per_user: Annotated[
        PositiveInt | None,
        Field(
            description="Limits the number of studies a user may have open concurently (disabled if NULL)",
        ),
    ] = None

    group_id: Annotated[
        int | None, Field(description="Groups associated to this product")
    ] = None
    support_standard_group_id: Annotated[
        int | None, Field(description="Support standard group ID, None if disabled")
    ] = None

    is_payment_enabled: Annotated[
        bool,
        Field(
            description="True if this product offers credits",
        ),
    ] = False

    credits_per_usd: Annotated[
        NonNegativeDecimal | None,
        Field(
            description="Price of the credits in this product given in credit/USD. None for free product.",
        ),
    ] = None

    min_payment_amount_usd: Annotated[
        NonNegativeDecimal | None,
        Field(
            description="Price of the credits in this product given in credit/USD. None for free product.",
        ),
    ] = None

    ## Guarantees when loaded from a database ---------------

    @field_validator("*", mode="before")
    @classmethod
    def _parse_empty_string_as_null(cls, v):
        """Safe measure: database entries are sometimes left blank instead of null"""
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
        return v

    @field_validator("name", mode="before")
    @classmethod
    def _check_is_valid_product_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            msg = f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            raise ValueError(msg)
        return v

    @field_serializer("issues", "vendor")
    @staticmethod
    def _preserve_snake_case(v: Any) -> Any:
        return v

    @property
    def twilio_alpha_numeric_sender_id(self) -> str:
        return self.short_name or self.display_name.replace(string.punctuation, "")[:11]

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        from sqlalchemy import Column

        schema.update(
            {
                "examples": [
                    {
                        # fake mandatory
                        "name": "osparc",
                        "host_regex": r"([\.-]{0,1}osparc[\.-])",
                        "twilio_messaging_sid": "1" * 34,
                        "registration_email_template": "osparc_registration_email",
                        "login_settings": {
                            "LOGIN_2FA_REQUIRED": False,
                        },
                        # defaults from sqlalchemy table
                        **{
                            str(c.name): c.server_default.arg  # type: ignore[union-attr]
                            for c in products.columns
                            if isinstance(c, Column)
                            and c.server_default
                            and isinstance(c.server_default.arg, str)  # type: ignore[union-attr]
                        },
                    },
                    # Example of data in the database with a url set with blanks
                    {
                        "name": "tis",
                        "display_name": "TI PT",
                        "short_name": "TIPI",
                        "host_regex": r"(^tis[\.-])|(^ti-solutions\.)|(^ti-plan\.)",
                        "support_email": "support@foo.com",
                        "manual_url": "https://foo.com",
                        "issues_login_url": None,
                        "issues_new_url": "https://foo.com/new",
                        "feedback_form_url": "",  # <-- blanks
                        "login_settings": {
                            "LOGIN_2FA_REQUIRED": False,
                        },
                    },
                    # Full example
                    {
                        "name": "osparc",
                        "display_name": "o²S²PARC FOO",
                        "short_name": "osparcf",
                        "host_regex": "([\\.-]{0,1}osparcf[\\.-])",
                        "support_email": "foo@osparcf.io",
                        "vendor": {
                            "url": "https://acme.com",
                            "license_url": "https://acme.com/license",
                            "invitation_form": True,
                            "name": "ACME",
                            "copyright": "© ACME correcaminos",
                            "ui": {
                                "logo_url": "https://acme.com/logo",
                                "strong_color": "#123456",
                                "project_alias": "study",
                            },
                        },
                        "issues": [
                            {
                                "label": "github",
                                "login_url": "https://github.com/ITISFoundation/osparc-simcore",
                                "new_url": "https://github.com/ITISFoundation/osparc-simcore/issues/new/choose",
                            },
                            {
                                "label": "fogbugz",
                                "login_url": "https://fogbugz.com/login",
                                "new_url": "https://fogbugz.com/new?project=123",
                            },
                        ],
                        "manuals": [
                            {"url": "doc.acme.com", "label": "main"},
                            {"url": "yet-another-manual.acme.com", "label": "z43"},
                        ],
                        "support": [
                            {
                                "url": "forum.acme.com",
                                "kind": "forum",
                                "label": "forum",
                            },
                            {
                                "kind": "email",
                                "email": "more-support@acme.com",
                                "label": "email",
                            },
                            {
                                "url": "support.acme.com",
                                "kind": "web",
                                "label": "web-form",
                            },
                        ],
                        "login_settings": {
                            "LOGIN_2FA_REQUIRED": False,
                        },
                        "group_id": 12345,
                        "is_payment_enabled": False,
                    },
                ]
            },
        )

    model_config = ConfigDict(
        alias_generator=snake_to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
        frozen=True,
        from_attributes=True,
        extra="ignore",
        json_schema_extra=_update_json_schema_extra,
    )

    def to_statics(self) -> dict[str, Any]:
        """
        Selects **public** fields from product's info
        and prefixes it with its name to produce
        items for statics.json (reachable by front-end)
        """

        # SECURITY WARNING: do not expose sensitive information here
        # keys will be named as e.g. displayName, supportEmail, ...
        return self.model_dump(
            include={
                "display_name": True,
                "support_email": True,
                "vendor": True,
                "issues": True,
                "manuals": True,
                "support": True,
                "is_payment_enabled": True,
                "is_dynamic_services_telemetry_enabled": True,
            },
            exclude_none=True,
            exclude_unset=True,
            by_alias=True,
        )

    def get_template_name_for(self, filename: str) -> str | None:
        """Checks for field marked with 'x_template_name' that fits the argument"""
        template_name = filename.removesuffix(".jinja2")
        for name, field in self.model_fields.items():
            if (
                field.json_schema_extra
                and field.json_schema_extra.get("x_template_name") == template_name  # type: ignore[union-attr]
            ):
                template_name_attribute: str = getattr(self, name)
                return template_name_attribute
        return None
