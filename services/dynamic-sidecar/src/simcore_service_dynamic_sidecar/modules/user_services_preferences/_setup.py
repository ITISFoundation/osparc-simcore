import logging

from fastapi import FastAPI
from servicelib.logging_utils import log_context

from ...core.settings import ApplicationSettings
from ._manager import UserServicesPreferencesManager
from ._utils import is_feature_enabled

_logger = logging.getLogger(__name__)


def setup_user_services_preferences(app: FastAPI) -> None:
    async def on_startup() -> None:
        with log_context(_logger, logging.INFO, "setup user services preferences"):
            if is_feature_enabled(app):
                settings: ApplicationSettings = app.state.settings
                assert settings.DY_SIDECAR_USER_PREFERENCES_PATH  # nosec
                assert settings.DY_SIDECAR_SERVICE_KEY  # nosec
                assert settings.DY_SIDECAR_SERVICE_VERSION  # nosec
                assert settings.DY_SIDECAR_PRODUCT_NAME  # nosec

                app.state.user_services_preferences_manager = (
                    UserServicesPreferencesManager(
                        user_preferences_path=settings.DY_SIDECAR_USER_PREFERENCES_PATH,
                        service_key=settings.DY_SIDECAR_SERVICE_KEY,
                        service_version=settings.DY_SIDECAR_SERVICE_VERSION,
                        user_id=settings.DY_SIDECAR_USER_ID,
                        product_name=settings.DY_SIDECAR_PRODUCT_NAME,
                    )
                )
            else:
                _logger.warning("user service preferences not mounted")

    app.add_event_handler("startup", on_startup)
