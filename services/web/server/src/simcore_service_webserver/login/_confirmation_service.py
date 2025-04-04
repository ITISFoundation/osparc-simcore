"""Confirmation codes/tokens tools

Codes are inserted in confirmation tables and they are associated to a user and an action
Used to validate some action (e.g. register, invitation, etc)
Codes can be used one time
Codes have expiration date (duration time is configurable)
"""

import logging
from datetime import datetime

from models_library.users import UserID

from ._login_repository_legacy import (
    ActionLiteralStr,
    AsyncpgStorage,
    ConfirmationTokenDict,
)
from .settings import LoginOptions

_logger = logging.getLogger(__name__)


async def get_or_create_confirmation_without_data(
    cfg: LoginOptions,
    db: AsyncpgStorage,
    user_id: UserID,
    action: ActionLiteralStr,
) -> ConfirmationTokenDict:

    confirmation: ConfirmationTokenDict | None = await db.get_confirmation(
        {"user": {"id": user_id}, "action": action}
    )

    if confirmation is not None and is_confirmation_expired(cfg, confirmation):
        await db.delete_confirmation(confirmation)
        _logger.warning(
            "Used expired token [%s]. Deleted from confirmations table.",
            confirmation,
        )
        confirmation = None

    if confirmation is None:
        confirmation = await db.create_confirmation(user_id, action=action)

    return confirmation


def get_expiration_date(
    cfg: LoginOptions, confirmation: ConfirmationTokenDict
) -> datetime:
    lifetime = cfg.get_confirmation_lifetime(confirmation["action"])
    return confirmation["created_at"] + lifetime


def is_confirmation_expired(cfg: LoginOptions, confirmation: ConfirmationTokenDict):
    age = datetime.utcnow() - confirmation["created_at"]
    lifetime = cfg.get_confirmation_lifetime(confirmation["action"])
    return age > lifetime


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
        _logger.warning(
            "Used expired token [%s]. Deleted from confirmations table.",
            confirmation,
        )
        return None
    return confirmation
