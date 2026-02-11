from collections.abc import Callable
from datetime import datetime
from typing import Literal, TypedDict

from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, SecretStr, ValidationInfo

from .constants import MSG_PASSWORD_MISMATCH

ActionLiteralStr = Literal["REGISTRATION", "INVITATION", "RESET_PASSWORD", "CHANGE_EMAIL"]


class BaseConfirmationTokenDict(TypedDict):
    code: str
    action: ActionLiteralStr


class ConfirmationTokenDict(BaseConfirmationTokenDict):
    # SEE packages/postgres-database/src/simcore_postgres_database/models/confirmations.py
    user_id: int
    created_at: datetime
    # SEE handlers_confirmation.py::email_confirmation to determine what type is associated to each action
    data: str | None


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


check_confirm_password_match = create_password_match_validator(reference_field="password")
