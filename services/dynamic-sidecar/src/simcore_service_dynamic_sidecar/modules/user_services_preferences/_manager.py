import logging
from pathlib import Path

from attr import dataclass
from fastapi import FastAPI

from ._utils import is_feature_enabled

_logger = logging.getLogger(__name__)


# TODO: connect to the database on demand, since we do not have a global connection
# and we don't want to have connections lying around
# same pattern is applied in nodeports


@dataclass
class UserServicesPreferencesManager:
    user_preferences_path: Path
    _preferences_already_saved: bool = False

    async def load_preferences(self) -> None:
        ...
        # TODO: finish implementation

    async def save_preferences(self) -> None:
        if self._preferences_already_saved:
            _logger.warning("Preferences were already saved, skipping save")
            return

        # TODO: finish implementation

        self._preferences_already_saved = True


async def save_user_services_preferences(app: FastAPI) -> None:
    if not is_feature_enabled(app):
        return

    user_services_preferences_manager: UserServicesPreferencesManager = (
        app.state.user_services_preferences_manager
    )
    await user_services_preferences_manager.save_preferences()


async def load_user_services_preferences(app: FastAPI) -> None:
    if not is_feature_enabled(app):
        return

    user_services_preferences_manager: UserServicesPreferencesManager = (
        app.state.user_services_preferences_manager
    )
    await user_services_preferences_manager.load_preferences()
