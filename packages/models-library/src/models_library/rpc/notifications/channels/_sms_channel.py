from typing import Literal

from pydantic import BaseModel
from pydantic_extra_types.phone_numbers import PhoneNumber


class SMSChannel(BaseModel):
    type: Literal["sms"] = "sms"

    phone_number: PhoneNumber
