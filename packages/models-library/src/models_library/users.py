from typing import Annotated, TypeAlias

from models_library.basic_types import IDStr
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints

UserID: TypeAlias = PositiveInt
UserNameID: TypeAlias = IDStr
GroupID: TypeAlias = PositiveInt


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
