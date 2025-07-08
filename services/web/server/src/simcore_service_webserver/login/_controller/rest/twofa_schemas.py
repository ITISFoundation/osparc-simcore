from typing import Literal

from models_library.emails import LowerCaseEmailStr
from pydantic import Field

from ..._models import InputSchema


class Resend2faBody(InputSchema):
    email: LowerCaseEmailStr = Field(..., description="User email (identifier)")
    via: Literal["SMS", "Email"] = "SMS"
