""" models for rest api schemas, i.e. those defined in openapi.json

"""


import pycountry
from models_library.api_schemas_webserver._base import InputSchema, OutputSchema
from models_library.emails import LowerCaseEmailStr
from pydantic import Field, validator
from simcore_postgres_database.models.users import UserStatus


class UserProfile(OutputSchema):
    first_name: str | None
    last_name: str | None
    email: LowerCaseEmailStr
    company_name: str | None
    phone: str | None
    address: str | None
    city: str | None
    state: str | None = Field(description="State, province, canton, ...")
    postal_code: str | None
    country: str | None

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


class PreUserProfile(InputSchema):
    first_name: str
    last_name: str
    email: LowerCaseEmailStr
    company_name: str | None
    phone: str | None
    # billing details
    address: str
    city: str
    state: str | None
    postal_code: str
    country: str

    @validator("country")
    @classmethod
    def valid_country(cls, v):
        if v:
            try:
                pycountry.countries.lookup(v)
            except LookupError as err:
                raise ValueError(v) from err
        return v


assert set(PreUserProfile.__fields__).issubset(UserProfile.__fields__)  # nosec
