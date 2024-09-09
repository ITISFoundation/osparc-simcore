from typing import TypeAlias

from pydantic import BaseModel, ConfigDict, ConstrainedStr, Field, PositiveInt

UserID: TypeAlias = PositiveInt
GroupID: TypeAlias = PositiveInt


class FirstNameStr(ConstrainedStr):
    strip_whitespace = True
    max_length = 255


class LastNameStr(FirstNameStr):
    ...


class UserBillingDetails(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    institution: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = Field(None, description="State, province, canton, ...")
    country: str
    postal_code: str | None = None
    phone: str | None = None
    model_config = ConfigDict(from_attributes=True)
