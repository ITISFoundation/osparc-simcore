from dataclasses import dataclass
from typing import Annotated, Final

from aiohttp import web
from annotated_types import doc

from ....security import security_web
from ....session.api import get_session

PENDING_2FA_EMAIL_KEY: Final[
    Annotated[
        str,
        doc("State of a login awaiting 2FA completion; written by auth_login, cleared on every successful login"),
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


async def set_pending_2fa_email(request: web.Request, *, email: str, phone_registration_allowed: bool) -> None:
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

    A login in progress takes precedence over the session's identity: a session
    authenticated with one account can start a login for another, and the second
    factor belongs to the account whose login is pending.

    Raises:
        web.HTTPUnauthorized: if the session has neither a pending 2FA email
            nor a completed login identity (i.e. it never started a login here)
    """
    session = await get_session(request)
    if pending := session.get(PENDING_2FA_EMAIL_KEY):
        return TrustedLoginEmail(
            email=pending["email"].lower(),
            fully_authenticated=False,
            phone_registration_allowed=pending["phone_registration_allowed"],
        )

    email = await security_web.get_identity(request)
    if email:
        assert "@" in email, f"Expected email as identity, got {email}"  # nosec
        return TrustedLoginEmail(email=email.lower(), fully_authenticated=True, phone_registration_allowed=True)

    raise web.HTTPUnauthorized(text=unauthorized_reason)
