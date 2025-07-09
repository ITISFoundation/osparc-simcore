from typing import Literal

from pydantic import BaseModel, EmailStr


class AccountRequestedEvent(BaseModel):
    type: Literal["account_requested"] = "account_requested"

    first_name: str
    last_name: str
    email: EmailStr

    # TODO: add more fields as needed


class AccountApprovedEvent(BaseModel):
    type: Literal["account_approved"] = "account_approved"


class AccountRejectedEvent(BaseModel):
    type: Literal["account_rejected"] = "account_rejected"

    reason: str
