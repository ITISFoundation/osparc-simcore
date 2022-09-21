""" Core functionality and tools for user's registration

    - registration code
    - invitation code
"""
import logging
from datetime import datetime
from typing import Any, Optional

from aiohttp import web
from pydantic import BaseModel, EmailStr, Field, PositiveInt, parse_raw_as
from servicelib.json_serialization import json_dumps
from yarl import URL

from ..db_models import UserStatus
from ._confirmation import (
    ConfirmationAction,
    get_expiration_date,
    is_confirmation_expired,
    validate_confirmation_code,
)
from .settings import LoginOptions
from .storage import AsyncpgStorage, ConfirmationTokenDict

log = logging.getLogger(__name__)


class ConfirmationTokenInfoDict(ConfirmationTokenDict):
    # TODO: as pydantic model?
    expires: datetime
    url: str


class InvitationData(BaseModel):
    created_by: EmailStr
    guest: EmailStr
    trial_account_days: Optional[PositiveInt] = Field(
        None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
    )


ACTION_TO_DATA_TYPE: dict[ConfirmationAction, Optional[type]] = {
    ConfirmationAction.INVITATION: InvitationData,
    ConfirmationAction.REGISTRATION: None,
}


async def check_registration(
    email: str,
    password: str,
    confirm: Optional[str],
    db: AsyncpgStorage,
    cfg: LoginOptions,
):
    # email : required & formats
    # password: required & secure[min length, ...]

    # If the email field is missing, return a 400 - HTTPBadRequest
    if email is None or password is None:
        raise web.HTTPBadRequest(
            reason="Email and password required", content_type="application/json"
        )

    if confirm and password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type="application/json"
        )

    # TODO: If the email field isn’t a valid email, return a 422 - HTTPUnprocessableEntity
    # TODO: If the password field is too short, return a 422 - HTTPUnprocessableEntity
    # TODO: use passwordmeter to enforce good passwords, but first create helper in front-end

    user = await db.get_user({"email": email})
    if user:
        # Resets pending confirmation if re-registers?
        if user["status"] == UserStatus.CONFIRMATION_PENDING.value:
            _confirmation: ConfirmationTokenDict = await db.get_confirmation(
                {"user": user, "action": ConfirmationAction.REGISTRATION.value}
            )

            if is_confirmation_expired(cfg, _confirmation):
                await db.delete_confirmation(_confirmation)
                await db.delete_user(user)
                return

        # If the email is already taken, return a 409 - HTTPConflict
        raise web.HTTPConflict(
            reason=cfg.MSG_EMAIL_EXISTS, content_type="application/json"
        )

    log.debug("Registration data validated")


async def create_invitation(
    host: dict[str, Any],
    guest: str,
    db: AsyncpgStorage,
    trial_days: Optional[PositiveInt] = None,
) -> ConfirmationTokenDict:
    """Creates an invitation token for a guest to register in the platform and returns

        Creates and injects an invitation token in the confirmation table associated
        to the host user

    :param host: valid user that creates the invitation
    :type host: Dict-like
    :param guest: some description of the guest, e.g. email, name or a json
    """
    data_model = InvitationData.parse_obj(
        {
            "created_by": host["email"],
            "guest": guest,
            "trial_account_days": trial_days,
        }
    )
    confirmation = await db.create_confirmation(
        user=host,
        action=ConfirmationAction.INVITATION.name,
        data=data_model.json(),
    )
    return confirmation


async def check_invitation(
    invitation: Optional[str], db: AsyncpgStorage, cfg: LoginOptions
) -> Optional[ConfirmationTokenInfoDict]:
    """
    :raise web.HTTPForbidden if invalid
    """
    confirmation = None
    if invitation:
        confirmation = await validate_confirmation_code(invitation, db, cfg)

    if confirmation:
        invitation_token_info = get_confirmation_info(cfg, confirmation)
        assert (
            invitation_token_info["action"] == ConfirmationAction.INVITATION.name
        )  # nosec
        log.info(
            "Invitation token used. Deleting %s",
            json_dumps(invitation_token_info, indent=1),
        )
        await db.delete_confirmation(confirmation)
        return invitation_token_info

    else:

        raise web.HTTPForbidden(
            reason=(
                "Invalid invitation code."
                "Your invitation was already used or might have expired."
                "Please contact our support team to get a new one."
            )
        )


def get_confirmation_info(
    cfg: LoginOptions, confirmation: ConfirmationTokenDict
) -> ConfirmationTokenInfoDict:
    """
    Extends ConfirmationTokenDict by adding extra info and
    deserializing action's data entry
    """
    info = ConfirmationTokenInfoDict(**confirmation)

    action = ConfirmationAction(confirmation["action"])
    if (data_type := ACTION_TO_DATA_TYPE[action]) and (data := confirmation["data"]):
        info["data"] = parse_raw_as(data_type, data)

    # extra
    info["expires"] = get_expiration_date(cfg, confirmation)

    if confirmation["action"] == ConfirmationAction.INVITATION.name:
        info["url"] = f"{get_invitation_url(confirmation)}"

    return info


def get_invitation_url(
    confirmation: ConfirmationTokenDict, origin: Optional[URL] = None
) -> URL:
    """Creates a URL to invite a user for registration

    This URL is sent to the user via email

    The user clicks URL link and ends up in the front-end

    This URL appends a fragment for front-end that interprets as open registration page
    and append the invitation code in the API request body together with the data added by the user
    """
    code = confirmation["code"]
    is_invitation = confirmation["action"] == ConfirmationAction.INVITATION.name

    if origin is None or not is_invitation:
        origin = URL()

    # https://some-web-url.io/#/registration/?invitation={code}
    # NOTE: Uniform encoding in front-end fragments https://github.com/ITISFoundation/osparc-simcore/issues/1975
    return origin.with_fragment(f"/registration/?invitation={code}")
