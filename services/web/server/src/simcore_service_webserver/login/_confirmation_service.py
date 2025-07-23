"""Confirmation codes/tokens tools

Codes are inserted in confirmation tables and they are associated to a user and an action
Used to validate some action (e.g. register, invitation, etc)
Codes can be used one time
Codes have expiration date (duration time is configurable)
"""

import logging
from datetime import UTC, datetime

from models_library.users import UserID

from ._confirmation_repository import ConfirmationRepository
from ._models import ActionLiteralStr, Confirmation
from .settings import LoginOptions

_logger = logging.getLogger(__name__)


class ConfirmationService:
    """Service for managing confirmation tokens and codes."""

    def __init__(
        self,
        confirmation_repository: ConfirmationRepository,
        login_options: LoginOptions,
    ) -> None:
        self._repository = confirmation_repository
        self._options = login_options

    @property
    def options(self) -> LoginOptions:
        """Access to login options for testing purposes."""
        return self._options

    async def get_or_create_confirmation_without_data(
        self,
        user_id: UserID,
        action: ActionLiteralStr,
    ) -> Confirmation:
        """Get existing or create new confirmation token for user action."""
        confirmation = await self._repository.get_confirmation(
            filter_dict={"user_id": user_id, "action": action}
        )

        if confirmation is not None and self.is_confirmation_expired(confirmation):
            await self._repository.delete_confirmation(confirmation=confirmation)
            _logger.warning(
                "Used expired token [%s]. Deleted from confirmations table.",
                confirmation,
            )
            confirmation = None

        if confirmation is None:
            confirmation = await self._repository.create_confirmation(
                user_id=user_id, action=action
            )

        return confirmation

    def get_expiration_date(self, confirmation: Confirmation) -> datetime:
        """Get expiration date for confirmation token."""
        lifetime = self._options.get_confirmation_lifetime(confirmation.action)
        return confirmation.created_at + lifetime

    def is_confirmation_expired(self, confirmation: Confirmation) -> bool:
        """Check if confirmation token has expired."""
        age = datetime.now(tz=UTC) - confirmation.created_at
        lifetime = self._options.get_confirmation_lifetime(confirmation.action)
        return age > lifetime

    async def validate_confirmation_code(self, code: str) -> Confirmation | None:
        """Validate confirmation code and return confirmation if valid."""
        assert not code.startswith("***"), "forgot .get_secret_value()??"  # nosec

        confirmation = await self._repository.get_confirmation(
            filter_dict={"code": code}
        )
        if confirmation and self.is_confirmation_expired(confirmation):
            await self._repository.delete_confirmation(confirmation=confirmation)
            _logger.warning(
                "Used expired token [%s]. Deleted from confirmations table.",
                confirmation,
            )
            return None
        return confirmation
