""" Core functionality and tools for user's registration

    - registration code
    - invitation code
"""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Literal, Optional

from aiohttp import web
from models_library.basic_types import IdInt
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    Json,
    PositiveInt,
    ValidationError,
    parse_raw_as,
    validator,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from yarl import URL

from ..invitations import (
    InvalidInvitation,
    InvitationsServiceUnavailable,
    extract_invitation,
    is_service_invitation_code,
    validate_invitation_url,
)
from ._confirmation import (
    ConfirmationAction,
    get_expiration_date,
    is_confirmation_expired,
    validate_confirmation_code,
)
from ._constants import MSG_EMAIL_EXISTS, MSG_INVITATIONS_CONTACT_SUFFIX
from .settings import LoginOptions
from .storage import AsyncpgStorage, ConfirmationTokenDict
from .utils import CONFIRMATION_PENDING

log = logging.getLogger(__name__)


class ConfirmationTokenInfoDict(ConfirmationTokenDict):
    expires: datetime
    url: str


class InvitationData(BaseModel):
    issuer: Optional[str] = Field(
        None,
        description="Who has issued this invitation? (e.g. an email or a uid)",
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


async def check_other_registrations(
    email: str,
    db: AsyncpgStorage,
    cfg: LoginOptions,
) -> None:

    if user := await db.get_user({"email": email}):
        # An account already registered with this email
        #
        #  RULE 'drop_previous_registration': any unconfirmed account w/o confirmation or
        #  w/ an expired confirmation will get deleted and its account (i.e. email)
        #  can be overtaken by this new registration
        #
        if user["status"] == CONFIRMATION_PENDING:
            _confirmation = await db.get_confirmation(
                filter_dict={
                    "user": user,
                    "action": ConfirmationAction.REGISTRATION.value,
                }
            )
            drop_previous_registration = not _confirmation or is_confirmation_expired(
                cfg, _confirmation
            )
            if drop_previous_registration:
                if not _confirmation:
                    await db.delete_user(user=user)
                else:
                    await db.delete_confirmation_and_user(
                        user=user, confirmation=_confirmation
                    )

                log.warning(
                    "Re-registration of %s with expired %s"
                    "Deleting user and proceeding to a new registration",
                    f"{user=}",
                    f"{_confirmation=}",
                )
                return

        raise web.HTTPConflict(
            reason=MSG_EMAIL_EXISTS, content_type=MIMETYPE_APPLICATION_JSON
        )


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


@contextmanager
def _invitations_request_context(invitation_code: str) -> Iterator[URL]:
    """
    - composes url from code
    - handles invitations errors as HTTPForbidden, HTTPServiceUnavailable
    """
    try:
        url = get_invitation_url(
            confirmation=ConfirmationTokenDict(
                code=invitation_code, action=ConfirmationAction.INVITATION.name
            ),
            origin=URL("https://fakehost.io:8000"),
        )

        yield url

    except (ValidationError, InvalidInvitation) as err:
        raise web.HTTPForbidden(
            reason=f"{err}. {MSG_INVITATIONS_CONTACT_SUFFIX}",
            content_type=MIMETYPE_APPLICATION_JSON,
        )

    except InvitationsServiceUnavailable as err:
        raise web.HTTPServiceUnavailable(
            reason=f"{err}",
            content_type=MIMETYPE_APPLICATION_JSON,
        )


async def extract_email_from_invitation(
    app: web.Application,
    invitation_code: str,
) -> EmailStr:
    """Returns associated email"""
    with _invitations_request_context(invitation_code=invitation_code) as url:
        content = await extract_invitation(app, invitation_url=f"{url}")
        return content.guest


async def check_and_consume_invitation(
    invitation_code: str,
    guest_email: str,
    db: AsyncpgStorage,
    cfg: LoginOptions,
    app=web.Application,
) -> InvitationData:
    """Consumes invitation: the code is validated, the invitation retrieives and then deleted
       since it only has one use

    If valid, it returns InvitationData, otherwise it raises web.HTTPForbidden

    :raises web.HTTPForbidden
    """

    # service-type invitations
    if is_service_invitation_code(code=invitation_code):
        with _invitations_request_context(invitation_code=invitation_code) as url:
            content = await validate_invitation_url(
                app,
                guest_email=guest_email,
                invitation_url=f"{url}",
            )

            log.info("Consuming invitation from service:\n%s", content.json(indent=1))
            return InvitationData(
                issuer=content.issuer,
                guest=content.guest,
                trial_account_days=content.trial_account_days,
            )

    # database-type invitations

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
            + MSG_INVITATIONS_CONTACT_SUFFIX
        ),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


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
