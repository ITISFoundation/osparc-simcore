from typing import Any, Callable

from pydantic import BaseModel, Extra, SecretStr

from ._constants import MSG_PASSWORD_MISMATCH


class InputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.forbid
        allow_mutations = False


def create_password_match_validator(
    reference_field: str,
) -> Callable[[SecretStr, dict[str, Any]], SecretStr]:
    def _check(v: SecretStr, values: dict[str, Any]):
        if (
            v is not None
            and reference_field in values
            and v.get_secret_value() != values[reference_field].get_secret_value()
        ):
            raise ValueError(MSG_PASSWORD_MISMATCH)
        return v

    return _check


check_confirm_password_match = create_password_match_validator(
    reference_field="password"
)
