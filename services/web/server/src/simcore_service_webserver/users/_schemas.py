""" models for rest api schemas, i.e. those defined in openapi.json

"""


import sys
from typing import Any, Final

import pycountry
from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.emails import LowerCaseEmailStr
from pydantic import Field, root_validator, validator
from simcore_postgres_database.models.users import UserStatus


class UserProfile(OutputSchema):
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

    # user status
    registered: bool
    status: UserStatus | None

    @validator("status")
    @classmethod
    def _consistency_check(cls, v, values):
        registered = values["registered"]
        status = v
        if not registered and status is not None:
            msg = f"{registered=} and {status=} is not allowed"
            raise ValueError(msg)
        return v


MAX_BYTES_SIZE_EXTRAS: Final[int] = 512


class PreUserProfile(InputSchema):
    first_name: str
    last_name: str
    email: LowerCaseEmailStr
    institution: str | None = Field(None, description="company, university, ...")
    phone: str | None
    # billing details
    address: str
    city: str
    state: str | None
    postal_code: str
    country: str
    extras: dict[str, Any] = Field(
        default_factory=dict,
        description="Keeps extra information provided in the request form. At most MAX_NUM_EXTRAS fields",
    )

    class Config(InputSchema.Config):
        anystr_strip_whitespace = True
        max_anystr_length = 200

    @validator("country")
    @classmethod
    def _valid_country(cls, v):
        if v:
            try:
                pycountry.countries.lookup(v)
            except LookupError as err:
                raise ValueError(v) from err
        return v

    @root_validator(pre=True)
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
            set(cls.__fields__.keys())
            | {f.alias for f in cls.__fields__.values() if f.alias}
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


assert set(PreUserProfile.__fields__).issubset(UserProfile.__fields__)  # nosec
