import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.logging_utils import log_context

from ..._meta import APP_NAME
from ...core.settings import ApplicationSettings
from ._manager import UserServicesPreferencesManager
from ._utils import get_resolved_version, is_feature_enabled

_logger = logging.getLogger(__name__)


def configure_user_services_preferences(app_lifespan: LifespanManager[FastAPI]) -> None:
    @asynccontextmanager
    async def user_services_preferences_lifespan(app: FastAPI) -> AsyncIterator[None]:
        with log_context(_logger, logging.INFO, "setup user services preferences"):
            if is_feature_enabled(app):
                settings: ApplicationSettings = app.state.settings
                assert settings.DY_SIDECAR_USER_PREFERENCES_PATH  # nosec
                assert settings.DY_SIDECAR_SERVICE_KEY  # nosec
                assert settings.DY_SIDECAR_SERVICE_VERSION  # nosec
                assert settings.DY_SIDECAR_PRODUCT_NAME  # nosec

                user_preferences_path = (
                    settings.DYNAMIC_SIDECAR_DY_VOLUMES_MOUNT_DIR
                    / settings.DY_SIDECAR_USER_PREFERENCES_PATH.relative_to("/")
                )
                user_preferences_path.mkdir(parents=True, exist_ok=True)

                resolved_version = get_resolved_version(app)
                assert resolved_version is not None  # nosec

                app.state.user_services_preferences_manager = UserServicesPreferencesManager(
                    user_preferences_path=user_preferences_path,
                    service_key=settings.DY_SIDECAR_SERVICE_KEY,
                    resolved_version=resolved_version,
                    user_id=settings.DY_SIDECAR_USER_ID,
                    product_name=settings.DY_SIDECAR_PRODUCT_NAME,
                    application_name=f"{APP_NAME}-{settings.DY_SIDECAR_NODE_ID}",
                )
            else:
                _logger.warning("user service preferences not mounted")
        yield

    app_lifespan.add(user_services_preferences_lifespan)
