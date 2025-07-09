from typing import Literal

from pydantic import EmailStr

from .notifications import Event


class AccountRequestedEvent(Event):
    type: Literal["account.requested"] = "account.requested"

    first_name: str
    last_name: str
    email: EmailStr

    # TODO: add more fields as needed
