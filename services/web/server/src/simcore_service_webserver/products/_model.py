import logging
import string
from typing import Any, ClassVar, Pattern  # noqa: UP035

from models_library.basic_regex import (
    PUBLIC_VARIABLE_NAME_RE,
    TWILIO_ALPHANUMERIC_SENDER_ID_RE,
)
from models_library.basic_types import NonNegativeDecimal
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, Extra, Field, PositiveInt, validator
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
    ProductLoginSettingsDict,
    Vendor,
    WebFeedback,
)

from ..db.models import products
from ..statics._constants import FRONTEND_APPS_AVAILABLE

_logger = logging.getLogger(__name__)


class Product(BaseModel):
    """Model used to parse a row of pg product's table

    The info in this model is static and read-only

    SEE descriptions in packages/postgres-database/src/simcore_postgres_database/models/products.py
    """

    name: ProductName = Field(regex=PUBLIC_VARIABLE_NAME_RE)

    display_name: str = Field(..., description="Long display name")
    short_name: str | None = Field(
        None,
        regex=TWILIO_ALPHANUMERIC_SENDER_ID_RE,
        min_length=2,
        max_length=11,
        description="Short display name for SMS",
    )

    host_regex: Pattern = Field(..., description="Host regex")
    # NOTE: typing.Pattern is supported but not re.Pattern (SEE https://github.com/pydantic/pydantic/pull/4366)

    support_email: LowerCaseEmailStr = Field(
        ...,
        description="Main support email."
        " Other support emails can be defined under 'support' field",
    )

    twilio_messaging_sid: str | None = Field(
        default=None, min_length=34, max_length=34, description="Identifier for SMS"
    )

    vendor: Vendor | None = Field(
        None,
        description="Vendor information such as company name, address, copyright, ...",
    )

    issues: list[IssueTracker] | None = None

    manuals: list[Manual] | None = None

    support: list[Forum | EmailFeedback | WebFeedback] | None = Field(None)

    login_settings: ProductLoginSettingsDict = Field(
        ...,
        description="Product customization of login settings. "
        "Note that these are NOT the final plugin settings but those are obtained from login.settings.get_plugin_settings",
    )

    registration_email_template: str | None = Field(
        None, x_template_name="registration_email"
    )

    max_open_studies_per_user: PositiveInt | None = Field(
        default=None,
        description="Limits the number of studies a user may have open concurently (disabled if NULL)",
    )

    group_id: int | None = Field(
        default=None, description="Groups associated to this product"
    )

    is_payment_enabled: bool = Field(
        default=False,
        description="True if this product offers credits",
    )

    credits_per_usd: NonNegativeDecimal | None = Field(
        default=None,
        description="Price of the credits in this product given in credit/USD. None for free product.",
    )

    @validator("*", pre=True)
    @classmethod
    def parse_empty_string_as_null(cls, v):
        """Safe measure: database entries are sometimes left blank instead of null"""
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
        return v

    @validator("name", pre=True, always=True)
    @classmethod
    def validate_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            msg = f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            raise ValueError(msg)
        return v

    @property
    def twilio_alpha_numeric_sender_id(self) -> str:
        return self.short_name or self.display_name.replace(string.punctuation, "")[:11]

    class Config:
        alias_generator = snake_to_camel  # to export
        allow_population_by_field_name = True
        frozen = True  # read-only
        orm_mode = True
        extra = Extra.ignore
        schema_extra: ClassVar[dict[str, Any]] = {
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
                        c.name: c.server_default.arg
                        for c in products.columns
                        if c.server_default and isinstance(c.server_default.arg, str)
                    },
                },
                # Example of data in the dabase with a url set with blanks
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
                # full example
                {
                    "name": "osparc",
                    "display_name": "o²S²PARC FOO",
                    "short_name": "osparcf",
                    "host_regex": "([\\.-]{0,1}osparcf[\\.-])",
                    "support_email": "foo@osparcf.io",
                    "vendor": {
                        "url": "https://acme.com",
                        "license_url": "https://acme.com/license",
                        "name": "ACME",
                        "copyright": "© ACME correcaminos",
                        "has_landing_page": False,
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
                    "is_payment_enabled": True,
                },
            ]
        }

    #  helpers ----

    def to_statics(self) -> dict[str, Any]:
        """
        Selects **public** fields from product's info
        and prefixes it with its name to produce
        items for statics.json (reachable by front-end)
        """

        # SECURITY WARNING: do not expose sensitive information here
        # keys will be named as e.g. displayName, supportEmail, ...
        return self.dict(
            include={
                "display_name",
                "support_email",
                "vendor",
                "issues",
                "manuals",
                "support",
                "is_payment_enabled",
            },
            exclude_none=True,
            exclude_unset=True,
            by_alias=True,
        )

    def get_template_name_for(self, filename: str) -> str | None:
        """Checks for field marked with 'x_template_name' that fits the argument"""
        template_name = filename.removesuffix(".jinja2")
        for field in self.__fields__.values():
            if field.field_info.extra.get("x_template_name") == template_name:
                template_name_attribute: str = getattr(self, field.name)
                return template_name_attribute
        return None
