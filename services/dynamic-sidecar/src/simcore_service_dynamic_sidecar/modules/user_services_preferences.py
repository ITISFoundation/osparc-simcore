import logging
from pathlib import Path

from attr import dataclass
from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


@dataclass
class UserServicesPreferencesManager:
    user_preferences_path: Path

    async def load_preferences(self) -> None:
        ...
        # TODO: finish implementation

    async def save_preferences(self) -> None:
        ...
        # TODO: finish implementation


def _is_feature_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    return (
        settings.DY_SIDECAR_SERVICE_KEY is not None
        and settings.DY_SIDECAR_SERVICE_VERSION is not None
        and settings.DY_SIDECAR_USER_PREFERENCES_PATH is not None
    )


async def save_user_services_preferences(app: FastAPI) -> None:
    if not _is_feature_enabled(app):
        return

    user_services_preferences_manager: UserServicesPreferencesManager = (
        app.state.user_services_preferences_manager
    )
    await user_services_preferences_manager.save_preferences()


async def load_user_services_preferences(app: FastAPI) -> None:
    if not _is_feature_enabled(app):
        return

    user_services_preferences_manager: UserServicesPreferencesManager = (
        app.state.user_services_preferences_manager
    )
    await user_services_preferences_manager.load_preferences()


def setup_user_services_preferences(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(_logger, logging.INFO, "setup user services preferences"):
            if _is_feature_enabled(app):
                settings: ApplicationSettings = app.state.settings
                assert settings.DY_SIDECAR_USER_PREFERENCES_PATH  # nosec
                app.state.user_services_preferences_manager = (
                    UserServicesPreferencesManager(
                        settings.DY_SIDECAR_USER_PREFERENCES_PATH
                    )
                )
            else:
                _logger.warning("user service preferences not mounted")

    async def on_shutdown() -> None:
        with log_context(_logger, logging.INFO, "shutdown user services preferences"):
            ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
