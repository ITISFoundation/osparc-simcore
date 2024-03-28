from typing import TypeAlias

from pydantic import BaseModel, ConstrainedStr, Field, PositiveInt

UserID: TypeAlias = PositiveInt
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
    country: str
    postal_code: str | None
    phone: str | None

    class Config:
        orm_mode = True
