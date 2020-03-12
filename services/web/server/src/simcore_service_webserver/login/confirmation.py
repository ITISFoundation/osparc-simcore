""" Confirmation codes/tokens tools

    Codes are inserted in confirmation tables and they are associated to a user and an action
    Used to validate some action (e.g. register, invitation, etc)
    Codes can be used one time
    Codes have expiration date (duration time is configurable)
"""
import logging
from datetime import datetime, timedelta

from ..db_models import ConfirmationAction
from .cfg import cfg

log = logging.getLogger(__name__)


async def validate_confirmation_code(code, db):
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


async def make_confirmation_link(request, confirmation):
    link = request.app.router["auth_confirmation"].url_for(code=confirmation["code"])
    return "{}://{}{}".format(request.scheme, request.host, link)


def get_expiration_date(confirmation):
    lifetime = get_confirmation_lifetime(confirmation)
    estimated_expiration = confirmation["created_at"] + lifetime
    return estimated_expiration


async def is_confirmation_allowed(user, action):
    db = cfg.STORAGE
    confirmation = await db.get_confirmation({"user": user, "action": action})
    if not confirmation:
        return True
    if is_confirmation_expired(confirmation):
        await db.delete_confirmation(confirmation)
        return True


def is_confirmation_expired(confirmation):
    age = datetime.utcnow() - confirmation["created_at"]
    lifetime = get_confirmation_lifetime(confirmation)
    return age > lifetime


def get_confirmation_lifetime(confirmation):
    lifetime_days = cfg[
        "{}_CONFIRMATION_LIFETIME".format(confirmation["action"].upper())
    ]
    lifetime = timedelta(days=lifetime_days)
    return lifetime


__all__ = ("ConfirmationAction",)
