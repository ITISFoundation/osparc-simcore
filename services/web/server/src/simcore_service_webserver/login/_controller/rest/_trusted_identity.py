from dataclasses import dataclass
from typing import Annotated, Final

from aiohttp import web
from aiohttp_security.api import IDENTITY_KEY
from annotated_types import doc

from ....session.api import get_session

PENDING_2FA_EMAIL_KEY: Final[
    Annotated[
        str,
        doc("state of a login awaiting 2FA completion; written by auth_login, cleared once the second factor succeeds"),
    ]
] = f"{__name__}.pending_2fa_email"


@dataclass(frozen=True, kw_only=True)
class TrustedLoginEmail:
    email: str
    # True when the session already completed a login (identity in session)
    fully_authenticated: bool
    # True when a login that has not passed 2FA yet may register a phone number
    # for the account: only when auth_login asked for it (SMS account without a
    # phone number). Prevents choosing the SMS channel for an account that does
    # not use it (e.g. an email-2FA account).
    phone_registration_allowed: bool


async def set_pending_2fa_email(request: web.Request, *, email: str, phone_registration_allowed: bool = False) -> None:
    session = await get_session(request)
    session[PENDING_2FA_EMAIL_KEY] = {
        "email": email.lower(),
        "phone_registration_allowed": phone_registration_allowed,
    }


async def clear_pending_2fa_email(request: web.Request) -> None:
    session = await get_session(request)
    session.pop(PENDING_2FA_EMAIL_KEY, None)


async def get_trusted_login_email(request: web.Request, *, unauthorized_reason: str) -> TrustedLoginEmail:
    """Email of the account this session may act on in a 2FA flow

    2FA handlers act on it and never on an email from the request body.

    Raises:
        web.HTTPUnauthorized: if the session has neither a completed login identity
            nor a pending 2FA email (i.e. it never started a login here)
    """
    # the identity policy stores the user's email (see security/_identity_policy.py);
    # aiohttp_security.api.authorized_userid cannot be used here because the
    # authorization policy maps it to the user id
    identity_policy = request.config_dict[IDENTITY_KEY]
    email = await identity_policy.identify(request)
    if email:
        return TrustedLoginEmail(email=email.lower(), fully_authenticated=True, phone_registration_allowed=True)

    session = await get_session(request)
    pending = session.get(PENDING_2FA_EMAIL_KEY)
    if not pending:
        raise web.HTTPUnauthorized(text=unauthorized_reason)

    return TrustedLoginEmail(
        email=pending["email"].lower(),
        fully_authenticated=False,
        phone_registration_allowed=pending["phone_registration_allowed"],
    )
