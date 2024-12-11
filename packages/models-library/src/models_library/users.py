from typing import Annotated, TypeAlias
from uuid import UUID

from models_library.basic_types import IDStr
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints

UserID: TypeAlias = PositiveInt
UserNameID: TypeAlias = IDStr


FirstNameStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255)
]

LastNameStr: TypeAlias = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=255)
]


class UserBillingDetails(BaseModel):
    first_name: str | None
    last_name: str | None
    institution: str | None
    address: str | None
    city: str | None
    state: str | None = Field(description="State, province, canton, ...")
    country: str  # Required for taxes
    postal_code: str | None
    phone: str | None

    model_config = ConfigDict(from_attributes=True)


#
# THIRD-PARTY TOKENS
#


class UserThirdPartyToken(BaseModel):
    """
    Tokens used to access third-party services connected to osparc (e.g. pennsieve, scicrunch, etc)
    """

    service: str
    token_key: UUID
    token_secret: UUID | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "service": "github-api-v1",
                "token_key": "5f21abf5-c596-47b7-bfd1-c0e436ef1107",
            }
        }
    )


#
# PERMISSIONS
#


class UserPermission(BaseModel):
    name: str
    allowed: bool
