from contextlib import suppress
from json import JSONDecodeError

from models_library.emails import LowerCaseEmailStr
from pydantic import (
    BaseModel,
    Field,
    PositiveInt,
    SecretStr,
    ValidationError,
    field_validator,
)

from ..._invitations_service import ConfirmedInvitationData
from ..._login_repository_legacy import (
    ConfirmationTokenDict,
)
from ..._models import InputSchema, check_confirm_password_match


class CodePathParam(BaseModel):
    code: SecretStr


def parse_extra_credits_in_usd_or_none(
    confirmation: ConfirmationTokenDict,
) -> PositiveInt | None:
    with suppress(ValidationError, JSONDecodeError):
        confirmation_data = confirmation.get("data", "EMPTY") or "EMPTY"
        invitation = ConfirmedInvitationData.model_validate_json(confirmation_data)
        return invitation.extra_credits_in_usd
    return None


class PhoneConfirmationBody(InputSchema):
    email: LowerCaseEmailStr
    phone: str = Field(
        ..., description="Phone number E.164, needed on the deployments with 2FA"
    )
    code: SecretStr


class ResetPasswordConfirmation(InputSchema):
    password: SecretStr
    confirm: SecretStr

    _password_confirm_match = field_validator("confirm")(check_confirm_password_match)
