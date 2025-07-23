from collections.abc import Callable
from datetime import datetime
from typing import Literal

from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationInfo

from .constants import MSG_PASSWORD_MISMATCH

ActionLiteralStr = Literal[
    "REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"
]


class Confirmation(BaseModel):
    code: str
    user_id: UserID
    action: ActionLiteralStr
    data: str | None = None
    created_at: datetime


class InputSchema(BaseModel):
    model_config = ConfigDict(
        populate_by_name=False,
        extra="forbid",
        frozen=True,
    )


def create_password_match_validator(
    reference_field: str,
) -> Callable[[SecretStr, ValidationInfo], SecretStr]:
    def _check(v: SecretStr, info: ValidationInfo):
        if (
            v is not None
            and reference_field in info.data
            and v.get_secret_value() != info.data[reference_field].get_secret_value()
        ):
            raise ValueError(MSG_PASSWORD_MISMATCH)
        return v

    return _check


check_confirm_password_match = create_password_match_validator(
    reference_field="password"
)
