""" Confirmation codes/tokens tools

    Codes are inserted in confirmation tables and they are associated to a user and an action
    Used to validate some action (e.g. register, invitation, etc)
    Codes can be used one time
    Codes have expiration date (duration time is configurable)
"""
import logging
from datetime import datetime
from typing import Any, Dict

from ..db_models import ConfirmationAction
from .settings import LoginOptions
from .storage import AsyncpgStorage

log = logging.getLogger(__name__)


async def validate_confirmation_code(code: str, db: AsyncpgStorage):
    confirmation = await db.get_confirmation({"code": code})
    if confirmation and is_confirmation_expired(confirmation):
        log.info(
            "Confirmation code '%s' %s. Deleting ...",
            code,
            "consumed" if confirmation else "expired",
        )
        await db.delete_confirmation(confirmation)
        confirmation = None
    return confirmation


def make_confirmation_link(request, confirmation) -> str:
    link = request.app.router["auth_confirmation"].url_for(code=confirmation["code"])
    return f"{request.scheme}://{request.host}{link}"


def get_expiration_date(cfg: LoginOptions, confirmation):
    lifetime = cfg.get_confirmation_lifetime(confirmation["action"])
    estimated_expiration = confirmation["created_at"] + lifetime
    return estimated_expiration


async def is_confirmation_allowed(cfg: LoginOptions, db: AsyncpgStorage, user, action):
    confirmation = await db.get_confirmation({"user": user, "action": action})
    if not confirmation:
        return True
    if is_confirmation_expired(cfg, confirmation):
        await db.delete_confirmation(confirmation)
        return True


def is_confirmation_expired(cfg: LoginOptions, confirmation: Dict[str, Any]):
    age = datetime.utcnow() - confirmation["created_at"]
    lifetime = cfg.get_confirmation_lifetime(confirmation["action"])
    return age > lifetime


__all__ = ("ConfirmationAction",)
