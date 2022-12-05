""" Core functionality and tools for user's registration

    - registration code
    - invitation code
"""

import logging
from datetime import datetime
from typing import Literal, Optional

from aiohttp import web
from models_library.basic_types import IdInt
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    Json,
    PositiveInt,
    ValidationError,
    parse_obj_as,
    parse_raw_as,
    validator,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
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
    expires: datetime
    url: str


class InvitationData(BaseModel):
    issuer: Optional[EmailStr] = Field(
        None, description="email of the person that issues this invitation"
    )
    guest: Optional[str] = Field(
        None, description="Reference tag for this invitation", deprecated=True
    )
    trial_account_days: Optional[PositiveInt] = Field(
        None,
        description="If set, this invitation will activate a trial account."
        "Sets the number of days from creation until the account expires",
    )


class _InvitationValidator(BaseModel):
    action: Literal[ConfirmationAction.INVITATION]
    data: Json[InvitationData]  # pylint: disable=unsubscriptable-object

    @validator("action", pre=True)
    @classmethod
    def ensure_enum(cls, v):
        if isinstance(v, ConfirmationAction):
            return v
        return ConfirmationAction(v)


ACTION_TO_DATA_TYPE: dict[ConfirmationAction, Optional[type]] = {
    ConfirmationAction.INVITATION: InvitationData,
    ConfirmationAction.REGISTRATION: None,
}


# TODO: use models in api/specs/webserver/scripts/openapi_auth.py  to validate and connect reponses in the OAS


def validate_email(email):
    try:
        parse_obj_as(EmailStr, email)
    except ValidationError as err:
        raise web.HTTPUnprocessableEntity(
            reason="Invalid email", content_type=MIMETYPE_APPLICATION_JSON
        ) from err
        # https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/422


async def validate_registration(
    email: str,
    password: str,
    confirm: Optional[str],
    db: AsyncpgStorage,
    cfg: LoginOptions,
) -> None:
    # email : required & formats
    # password: required & secure[min length, ...]

    if email is None or password is None:
        raise web.HTTPBadRequest(
            reason="Both email and password are required",
            content_type=MIMETYPE_APPLICATION_JSON,
        )  # https://developer.mozilla.org/en-US/docs/web/http/status/400

    if confirm and password != confirm:
        raise web.HTTPConflict(
            reason=cfg.MSG_PASSWORD_MISMATCH, content_type=MIMETYPE_APPLICATION_JSON
        )  # https://developer.mozilla.org/en-US/docs/web/http/status/409

    validate_email(email)

    #
    # NOTE: Extra requirements on passwords
    #
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2480
    #

    if user := await db.get_user({"email": email}):

        if user["status"] == UserStatus.CONFIRMATION_PENDING.value:
            _confirmation: ConfirmationTokenDict = await db.get_confirmation(
                {"user": user, "action": ConfirmationAction.REGISTRATION.value}
            )

            if is_confirmation_expired(cfg, _confirmation):
                # Confirmation has expired and therefore we treat this
                # request as a new registration. For that reason we need to
                # delete the user entry so it can be re-created.
                #

                # FIXME: deleting confirmation and user will delete associated projects!?
                # FIXME: Can a unconfirmed user be authorized to start projects or not?

                # FIXME: make atomic delete. Otherwise we might have unconfirmed users without
                # associated confirmation
                await db.delete_confirmation(_confirmation)
                await db.delete_user(user)

                log.warning(
                    "Re-registration of %s with expired %s"
                    "Deleting user and proceeding to a new registration",
                    f"{user=}",
                    f"{_confirmation=}",
                )
                return

        # The email is already taken !!
        raise web.HTTPConflict(
            reason=cfg.MSG_EMAIL_EXISTS, content_type=MIMETYPE_APPLICATION_JSON
        )  # https://developer.mozilla.org/en-US/docs/web/http/status/409

    log.debug("Registration data validated")


async def create_invitation_token(
    db: AsyncpgStorage,
    *,
    user_id: IdInt,
    user_email: Optional[EmailStr] = None,
    tag: Optional[str] = None,
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
            "issuer": user_email,
            "guest": tag,
            "trial_account_days": trial_days,
        }
    )
    confirmation = await db.create_confirmation(
        user_id=user_id,
        action=ConfirmationAction.INVITATION.name,
        data=data_model.json(),
    )
    return confirmation


async def check_and_consume_invitation(
    invitation_code: str, db: AsyncpgStorage, cfg: LoginOptions
) -> InvitationData:
    """Consumes invitation: the code is validated, the invitation retrieives and then deleted
       since it only has one use

    If valid, it returns InvitationData, otherwise it raises web.HTTPForbidden

    :raises web.HTTPForbidden
    """
    if confirmation_token := await validate_confirmation_code(invitation_code, db, cfg):
        try:
            invitation = _InvitationValidator.parse_obj(confirmation_token)
            return invitation.data

        except ValidationError as err:
            log.warning(
                "%s is associated with an invalid %s.\nDetails: %s",
                f"{invitation_code=}",
                f"{confirmation_token=}",
                f"{err=}",
            )

        finally:
            await db.delete_confirmation(confirmation_token)
            log.info("Invitation with %s was consumed", f"{confirmation_token=}")

    raise web.HTTPForbidden(
        reason=(
            "Invalid invitation code."
            "Your invitation was already used or might have expired."
            "Please contact our support team to get a new one."
        ),
        content_type=MIMETYPE_APPLICATION_JSON,
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
