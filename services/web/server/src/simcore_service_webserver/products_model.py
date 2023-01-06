import logging
import string
from typing import Any, Optional, Pattern, Union

from models_library.basic_regex import (
    PUBLIC_VARIABLE_NAME_RE,
    TWILIO_ALPHANUMERIC_SENDER_ID_RE,
)
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, EmailStr, Extra, Field, PositiveInt, validator
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
    ProductLoginSettings,
    Vendor,
    WebFeedback,
)

from .db_models import products
from .statics_constants import FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)


#
# MODEL
#


class Product(BaseModel):
    """Model used to parse a row of pg product's table

    The info in this model is static and read-only

    SEE descriptions in packages/postgres-database/src/simcore_postgres_database/models/products.py
    """

    name: str = Field(regex=PUBLIC_VARIABLE_NAME_RE)

    display_name: str = Field(..., description="Long display name")
    short_name: Optional[str] = Field(
        None,
        regex=TWILIO_ALPHANUMERIC_SENDER_ID_RE,
        min_length=2,
        max_length=11,
        description="Short display name for SMS",
    )

    host_regex: Pattern = Field(..., description="Host regex")

    support_email: EmailStr = Field(
        ...,
        description="Main support email."
        " Other support emails can be defined under 'support' field",
    )

    twilio_messaging_sid: Optional[str] = Field(
        default=None, min_length=34, max_length=34, description="Identifier for SMS"
    )

    vendor: Optional[Vendor] = Field(
        None,
        description="Vendor information such as company name, address, copyright, ...",
    )

    issues: Optional[list[IssueTracker]] = None

    manuals: Optional[list[Manual]] = None

    support: Optional[list[Union[Forum, EmailFeedback, WebFeedback]]] = Field(None)

    login_settings: ProductLoginSettings = Field(...)

    registration_email_template: Optional[str] = Field(
        None, x_template_name="registration_email"
    )

    max_open_studies_per_user: Optional[PositiveInt] = Field(
        default=None,
        description="Limits the number of studies a user may have open concurently (disabled if NULL)",
    )

    @validator("name", pre=True, always=True)
    @classmethod
    def validate_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            raise ValueError(
                f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            )
        return v

    @validator("*", pre=True)
    @classmethod
    def parse_empty_string_as_null(cls, v):
        """Safe measure: database entries are sometimes left blank instead of null"""
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
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
        schema_extra = {
            "examples": [
                {
                    # fake mandatory
                    "name": "osparc",
                    "host_regex": r"([\.-]{0,1}osparc[\.-])",
                    "twilio_messaging_sid": "1" * 34,
                    "registration_email_template": "osparc_registration_email",
                    "login_settings": {
                        "two_factor_enabled": False,
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
                        "two_factor_enabled": False,
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
                        "two_factor_enabled": False,
                    },
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
            },
            exclude_none=True,
            exclude_unset=True,
            by_alias=True,
        )

    def get_template_name_for(self, filename: str) -> Optional[str]:
        """Checks for field marked with 'x_template_name' that fits the argument"""
        template_name = filename.removesuffix(".jinja2")
        for field in self.__fields__.values():
            if field.field_info.extra.get("x_template_name") == template_name:
                return getattr(self, field.name)
        return None
