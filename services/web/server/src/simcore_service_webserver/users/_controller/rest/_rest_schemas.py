"""input/output datasets used in the rest-API

NOTE: Most of the model schemas are in `models_library.api_schemas_webserver.users`,
the rest (hidden or needs a dependency) is here
"""

import re
import sys
from contextlib import suppress
from typing import Annotated, Any, Final

import pycountry
from common_library.basic_types import DEFAULT_FACTORY
from models_library.api_schemas_webserver._base import InputSchema
from models_library.api_schemas_webserver.users import (
    FirstNameSafeStr,
    LastNameSafeStr,
    MyProfileAddressPatch,
    UserAccountGet,
)
from models_library.api_schemas_webserver.users import (
    MyProfileRestPatch as _MyProfileRestPatchBase,
)
from models_library.emails import LowerCaseEmailStr
from models_library.string_types import AddressLineSafeStr, DisplaySafeStr, PostalCodeSafeStr
from models_library.utils.common_validators import empty_str_to_none_pre_validator
from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from ....models import AuthenticatedRequestContext, PhoneNumberStr

MAX_BYTES_SIZE_EXTRAS: Final[int] = 512


class UsersRequestContext(AuthenticatedRequestContext): ...


#
# COUNTRY
#


def _normalize_country_name(v: str) -> str:
    # NOTE: requires installing `pycountry`
    if v:
        try:
            country = pycountry.countries.lookup(v)
        except LookupError as err:
            raise ValueError(v) from err
        return str(country.name)
    return v


type CountryNameStr = Annotated[str, BeforeValidator(_normalize_country_name)]


#
# PHONE REGISTRATION
#


class MyPhoneRegister(InputSchema):
    phone: Annotated[
        PhoneNumberStr,
        Field(description="Phone number to register"),
    ]


class MyPhoneConfirm(InputSchema):
    code: Annotated[
        str,
        StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9]+$"),
        Field(description="Alphanumeric confirmation code"),
    ]


#
# USER-ACCOUNT
#


class UserAccountRestPreRegister(InputSchema):
    first_name: FirstNameSafeStr
    last_name: LastNameSafeStr
    email: LowerCaseEmailStr
    institution: Annotated[DisplaySafeStr | None, Field(description="company, university, ...")] = None
    phone: Annotated[PhoneNumberStr | None, BeforeValidator(empty_str_to_none_pre_validator)]

    # billing details
    address: AddressLineSafeStr
    city: DisplaySafeStr
    state: DisplaySafeStr | None = None
    postal_code: PostalCodeSafeStr
    country: CountryNameStr
    extras: Annotated[
        dict[str, Any],
        Field(
            default_factory=dict,
            description="Keeps extra information provided in the request form.",
        ),
    ] = DEFAULT_FACTORY

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


assert set(UserAccountRestPreRegister.model_fields).issubset(  # nosec
    # asserts field names are in sync
    UserAccountGet.model_fields
)


#
# MY PROFILE
#


class MyProfileAddressRestPatch(MyProfileAddressPatch):
    institution: DisplaySafeStr | None = None
    address: AddressLineSafeStr | None = None
    city: DisplaySafeStr | None = None
    state: DisplaySafeStr | None = None
    postal_code: PostalCodeSafeStr | None = None
    country: CountryNameStr | None = None


class MyProfileRestPatch(_MyProfileRestPatchBase):
    contact: MyProfileAddressRestPatch | None = None
