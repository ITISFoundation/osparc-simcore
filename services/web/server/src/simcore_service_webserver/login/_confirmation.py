""" Confirmation codes/tokens tools

    Codes are inserted in confirmation tables and they are associated to a user and an action
    Used to validate some action (e.g. register, invitation, etc)
    Codes can be used one time
    Codes have expiration date (duration time is configurable)
"""
import logging
from datetime import datetime

from aiohttp import web
from yarl import URL

from ..db.models import ConfirmationAction
from .settings import LoginOptions
from .storage import AsyncpgStorage, ConfirmationTokenDict

log = logging.getLogger(__name__)


async def validate_confirmation_code(
    code: str, db: AsyncpgStorage, cfg: LoginOptions
) -> ConfirmationTokenDict | None:
    """
    Returns None if validation fails
    """
    assert not code.startswith("***"), "forgot .get_secret_value()??"  # nosec

    confirmation: ConfirmationTokenDict | None = await db.get_confirmation(
        {"code": code}
    )
    if confirmation and is_confirmation_expired(cfg, confirmation):
        await db.delete_confirmation(confirmation)
        log.warning(
            "Used expired token [%s]. Deleted from confirmations table.",
            confirmation,
        )
        return None
    return confirmation


def _url_for_confirmation(app: web.Application, code: str) -> URL:
    return app.router["auth_confirmation"].url_for(code=code)


def make_confirmation_link(
    request: web.Request, confirmation: ConfirmationTokenDict
) -> str:
    link = _url_for_confirmation(request.app, code=confirmation["code"])
    return f"{request.scheme}://{request.host}{link}"


def get_expiration_date(
    cfg: LoginOptions, confirmation: ConfirmationTokenDict
) -> datetime:
    lifetime = cfg.get_confirmation_lifetime(confirmation["action"])
    return confirmation["created_at"] + lifetime


async def is_confirmation_allowed(
    cfg: LoginOptions, db: AsyncpgStorage, user, action: ConfirmationAction
):
    confirmation: ConfirmationTokenDict = await db.get_confirmation(
        {"user": user, "action": action}
    )
    if not confirmation:
        return True
    if is_confirmation_expired(cfg, confirmation):
        await db.delete_confirmation(confirmation)
        log.warning(
            "Used expired token [%s]. Deleted from confirmations table.",
            confirmation,
        )
        return True
    return False


def is_confirmation_expired(cfg: LoginOptions, confirmation: ConfirmationTokenDict):
    age = datetime.utcnow() - confirmation["created_at"]
    lifetime = cfg.get_confirmation_lifetime(confirmation["action"])
    return age > lifetime
