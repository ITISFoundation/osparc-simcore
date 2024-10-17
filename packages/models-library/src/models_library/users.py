from typing import Annotated, Final, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    TypeAdapter,
)

UserID: TypeAlias = PositiveInt
GroupID: TypeAlias = PositiveInt
GroupIDAdapter: Final[TypeAdapter[GroupID]] = TypeAdapter(GroupID)


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
