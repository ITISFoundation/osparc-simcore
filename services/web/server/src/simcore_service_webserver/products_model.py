import logging
import string
from typing import Any, Optional, Pattern, Union

from models_library.basic_regex import (
    PUBLIC_VARIABLE_NAME_RE,
    TWILIO_ALPHANUMERIC_SENDER_ID_RE,
)
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, EmailStr, Field, validator
from simcore_postgres_database.models.products import (
    EmailFeedback,
    Forum,
    IssueTracker,
    Manual,
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
    display_name: str
    short_name: Optional[str] = Field(
        None, regex=TWILIO_ALPHANUMERIC_SENDER_ID_RE, min_length=2, max_length=11
    )
    host_regex: Pattern

    # EMAILS/PHONE
    support_email: EmailStr
    twilio_messaging_sid: Optional[str] = Field(
        default=None,
        min_length=34,
        max_length=34,
    )

    vendor: Optional[Vendor] = Field(
        None,
        description="Read-only information about the vendor"
        "E.g. company name, address, copyright, etc",
    )

    issues: list[IssueTracker]

    manuals: list[Manual]

    support: list[Union[Forum, EmailFeedback, WebFeedback]]

    # TEMPLATES
    registration_email_template: Optional[str] = Field(
        None, x_template_name="registration_email"
    )

    class Config:
        orm_mode = True
        frozen = True  # read-only
        schema_extra = {
            "examples": [
                {
                    # fake mandatory
                    "name": "osparc",
                    "host_regex": r"([\.-]{0,1}osparc[\.-])",
                    "twilio_messaging_sid": "1" * 34,
                    "registration_email_template": "osparc_registration_email",
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
                },
                {
                    # fake mandatory
                    "name": "s4llite",
                    "host_regex": r"([\.-]{0,1}acme[\.-])",
                    "twilio_messaging_sid": "1" * 34,
                    "registration_email_template": "osparc_registration_email",
                    "display_name": "FOOO",
                    "support_email": "foo@foo.com",
                    "manual_url": "https://themanula.com",
                    # optionals
                    "vendor": {
                        "name": "ACME",
                        "address": "sesame street",
                        "copyright": "© ACME correcaminos",
                        "url": "https://acme.com",
                        "forum_url": "https://forum.acme.com",
                    },
                },
            ]
        }

    @validator("name", pre=True, always=True)
    @classmethod
    def validate_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            raise ValueError(
                f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            )
        return v

    @validator(
        "*",
        pre=True,
    )
    @classmethod
    def parse_empty_string_as_null(cls, v):
        """Safe measure: database entries are sometimes left blank instead of null"""
        if isinstance(v, str) and len(v.strip()) == 0:
            return None
        return v

    @property
    def twilio_alpha_numeric_sender_id(self) -> str:
        return self.short_name or self.display_name.replace(string.punctuation, "")[:11]

    def to_statics(self) -> dict[str, Any]:
        """
        Selects **public** fields from product's info
        and prefixes it with its name to produce
        items for statics.json (reachable by front-end)
        """
        # SECURITY WARNING: do not expose sensitive information here
        public_selection = self.dict(
            include={"display_name", "support_email", "issues", "manuals", "support"},
            exclude_none=True,
        )
        # keys will be named as e.g. DisplayName, SupportEmail, ...
        return {snake_to_camel(key): value for key, value in public_selection.items()}

    def get_template_name_for(self, filename: str) -> Optional[str]:
        """Checks for field marked with 'x_template_name' that fits the argument"""
        template_name = filename.removesuffix(".jinja2")
        for field in self.__fields__.values():
            if field.field_info.extra.get("x_template_name") == template_name:
                return getattr(self, field.name)
        return None
