from models_library.emails import LowerCaseEmailStr
from pydantic import SecretStr, field_validator

from ..._models import InputSchema, create_password_match_validator


class ResetPasswordBody(InputSchema):
    email: LowerCaseEmailStr


class ChangeEmailBody(InputSchema):
    email: LowerCaseEmailStr


class ChangePasswordBody(InputSchema):
    current: SecretStr
    new: SecretStr
    confirm: SecretStr

    _password_confirm_match = field_validator("confirm")(
        create_password_match_validator(reference_field="new")
    )
