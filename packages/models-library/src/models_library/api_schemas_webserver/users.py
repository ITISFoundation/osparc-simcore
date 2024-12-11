import re
import sys
from contextlib import suppress
from datetime import date
from enum import Enum
from typing import Annotated, Any, Final, Literal

import pycountry
from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.api_schemas_webserver.groups import MyGroupsGet
from models_library.api_schemas_webserver.users_preferences import AggregatedPreferences
from models_library.basic_types import IDStr
from models_library.emails import LowerCaseEmailStr
from models_library.products import ProductName
from models_library.users import FirstNameStr, LastNameStr, UserID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)
from simcore_postgres_database.models.users import UserStatus

from ._base import InputSchema, OutputSchema


class MyProfilePrivacyGet(OutputSchema):
    hide_fullname: bool
    hide_email: bool


class MyProfilePrivacyPatch(InputSchema):
    hide_fullname: bool | None = None
    hide_email: bool | None = None


class MyProfileGet(BaseModel):
    # WARNING: do not use InputSchema until front-end is updated!
    id: UserID
    user_name: Annotated[
        IDStr, Field(description="Unique username identifier", alias="userName")
    ]
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None
    login: LowerCaseEmailStr

    role: Literal["ANONYMOUS", "GUEST", "USER", "TESTER", "PRODUCT_OWNER", "ADMIN"]
    groups: MyGroupsGet | None = None
    gravatar_id: Annotated[str | None, Field(deprecated=True)] = None

    expiration_date: Annotated[
        date | None,
        Field(
            description="If user has a trial account, it sets the expiration date, otherwise None",
            alias="expirationDate",
        ),
    ] = None

    privacy: MyProfilePrivacyGet
    preferences: AggregatedPreferences

    model_config = ConfigDict(
        # NOTE: old models have an hybrid between snake and camel cases!
        # Should be unified at some point
        populate_by_name=True,
        json_schema_extra={
            "examples": [
                {
                    "id": 42,
                    "login": "bla@foo.com",
                    "userName": "bla42",
                    "role": "admin",  # pre
                    "expirationDate": "2022-09-14",  # optional
                    "preferences": {},
                    "privacy": {"hide_fullname": 0, "hide_email": 1},
                },
            ]
        },
    )

    @field_validator("role", mode="before")
    @classmethod
    def _to_upper_string(cls, v):
        if isinstance(v, str):
            return v.upper()
        if isinstance(v, Enum):
            return v.name.upper()
        return v


class MyProfilePatch(BaseModel):
    # WARNING: do not use InputSchema until front-end is updated!
    first_name: FirstNameStr | None = None
    last_name: LastNameStr | None = None
    user_name: Annotated[IDStr | None, Field(alias="userName")] = None

    privacy: MyProfilePrivacyPatch | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "first_name": "Pedro",
                "last_name": "Crespo",
            }
        }
    )

    @field_validator("user_name")
    @classmethod
    def _validate_user_name(cls, value: str):
        # Ensure valid characters (alphanumeric + . _ -)
        if not re.match(r"^[a-zA-Z][a-zA-Z0-9._-]*$", value):
            msg = f"Username '{value}' must start with a letter and can only contain letters, numbers and '_', '.' or '-'."
            raise ValueError(msg)

        # Ensure no consecutive special characters
        if re.search(r"[_.-]{2,}", value):
            msg = f"Username '{value}' cannot contain consecutive special characters like '__'."
            raise ValueError(msg)

        # Ensure it doesn't end with a special character
        if {value[0], value[-1]}.intersection({"_", "-", "."}):
            msg = f"Username '{value}' cannot end or start with a special character."
            raise ValueError(msg)

        # Check reserved words (example list; extend as needed)
        reserved_words = {
            "admin",
            "root",
            "system",
            "null",
            "undefined",
            "support",
            "moderator",
            # NOTE: add here extra via env vars
        }
        if any(w in value.lower() for w in reserved_words):
            msg = f"Username '{value}' cannot be used."
            raise ValueError(msg)

        return value


class SearchQueryParams(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=200,
        description="complete or glob pattern for an email",
    )


class UserGet(OutputSchema):
    first_name: str | None
    last_name: str | None
    email: LowerCaseEmailStr
    institution: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: str | None = Field(description="State, province, canton, ...")
    postal_code: str | None
    country: str | None
    extras: dict[str, Any] = Field(
        default_factory=dict,
        description="Keeps extra information provided in the request form",
    )

    # authorization
    invited_by: str | None = Field(default=None)

    # user status
    registered: bool
    status: UserStatus | None
    products: list[ProductName] | None = Field(
        default=None,
        description="List of products this users is included or None if fields is unset",
    )

    @field_validator("status")
    @classmethod
    def _consistency_check(cls, v, info: ValidationInfo):
        registered = info.data["registered"]
        status = v
        if not registered and status is not None:
            msg = f"{registered=} and {status=} is not allowed"
            raise ValueError(msg)
        return v


MAX_BYTES_SIZE_EXTRAS: Final[int] = 512


class PreRegisteredUserGet(InputSchema):
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
            description="Keeps extra information provided in the request form. At most MAX_NUM_EXTRAS fields",
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


assert set(PreRegisteredUserGet.model_fields).issubset(UserGet.model_fields)  # nosec
