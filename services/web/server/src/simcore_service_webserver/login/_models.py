from pydantic import BaseModel, Extra, SecretStr

from ._constants import MSG_PASSWORD_MISMATCH


class InputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.forbid
        allow_mutations = False


def check_confirm_password_match(v: SecretStr, values):
    if (
        v is not None
        and "password" in values
        and v.get_secret_value() != values["password"].get_secret_value()
    ):
        raise ValueError(MSG_PASSWORD_MISMATCH)
    return v
