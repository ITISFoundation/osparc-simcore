"""input/output datasets used in the rest-API

NOTE: Most of the model schemas are in `models_library.api_schemas_webserver.users`,
the rest (hidden or needs a dependency) is here
"""

import re
import sys
from contextlib import suppress
from typing import Annotated, Any, Final

import pycountry
from models_library.api_schemas_webserver._base import InputSchema
from models_library.api_schemas_webserver.users import UserAccountGet
from models_library.emails import LowerCaseEmailStr
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from servicelib.request_keys import RQT_USERID_KEY

from ....constants import RQ_PRODUCT_KEY


class UsersRequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


MAX_BYTES_SIZE_EXTRAS: Final[int] = 512


class PreRegisteredUserGet(InputSchema):
    # NOTE: validators need pycountry!

    first_name: str
    last_name: str
    email: LowerCaseEmailStr
    institution: str | None = Field(
        default=None, description="company, university, ..."
    )
    phone: str | None
    # billing details
    address: str
    city: str
    state: str | None = Field(default=None)
    postal_code: str
    country: str
    extras: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Keeps extra information provided in the request form.",
        ),
    ]

    model_config = ConfigDict(str_strip_whitespace=True, str_max_length=200)

    @model_validator(mode="before")
    @classmethod
    def _preprocess_aliases_and_extras(cls, values):
        # multiple aliases for "institution"
        alias_by_priority = ("companyName", "company", "university", "universityName")
        if "institution" not in values:

            for alias in alias_by_priority:
                if alias in values:
                    values["institution"] = values.pop(alias)

        # collect extras
        extra_fields = {}
        field_names_and_aliases = (
            set(cls.model_fields.keys())
            | {f.alias for f in cls.model_fields.values() if f.alias}
            | set(alias_by_priority)
        )
        for key, value in values.items():
            if key not in field_names_and_aliases:
                extra_fields[key] = value
                if sys.getsizeof(extra_fields) > MAX_BYTES_SIZE_EXTRAS:
                    extra_fields.pop(key)
                    break

        for key in extra_fields:
            values.pop(key)

        values.setdefault("extras", {})
        values["extras"].update(extra_fields)

        return values

    @field_validator("first_name", "last_name", "institution", mode="before")
    @classmethod
    def _pre_normalize_given_names(cls, v):
        if v:
            with suppress(Exception):  # skip if funny characters
                name = re.sub(r"\s+", " ", v)
                return re.sub(r"\b\w+\b", lambda m: m.group(0).capitalize(), name)
        return v

    @field_validator("country", mode="before")
    @classmethod
    def _pre_check_and_normalize_country(cls, v):
        if v:
            try:
                return pycountry.countries.lookup(v).name
            except LookupError as err:
                raise ValueError(v) from err
        return v


# asserts field names are in sync
assert set(PreRegisteredUserGet.model_fields).issubset(
    UserAccountGet.model_fields
)  # nosec
