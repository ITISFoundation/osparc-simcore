from typing import Callable

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationInfo

from ._constants import MSG_PASSWORD_MISMATCH


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
