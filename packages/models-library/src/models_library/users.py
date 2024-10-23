from typing import TypeAlias

from models_library.basic_types import IDStr
from pydantic import BaseModel, ConstrainedStr, Field, PositiveInt

UserID: TypeAlias = PositiveInt
UserNameID: TypeAlias = IDStr
GroupID: TypeAlias = PositiveInt


class FirstNameStr(ConstrainedStr):
    strip_whitespace = True
    max_length = 255


class LastNameStr(FirstNameStr):
    ...


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

    class Config:
        orm_mode = True
