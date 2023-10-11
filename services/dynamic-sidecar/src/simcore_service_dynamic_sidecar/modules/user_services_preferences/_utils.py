import logging

from fastapi import FastAPI

from ...core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def is_feature_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    is_enabled = (
        settings.DY_SIDECAR_SERVICE_KEY is not None
        and settings.DY_SIDECAR_SERVICE_VERSION is not None
        and settings.DY_SIDECAR_USER_PREFERENCES_PATH is not None
        and settings.DY_SIDECAR_PRODUCT_NAME is not None
        and settings.POSTGRES_SETTINGS is not None
    )
    if not is_enabled:
        _logger.warning(
            "user services preferences is manager is not enabled: %s, %s, %s, %s, %s",
            f"{settings.DY_SIDECAR_SERVICE_KEY=}",
            f"{settings.DY_SIDECAR_SERVICE_VERSION=}",
            f"{settings.DY_SIDECAR_USER_PREFERENCES_PATH=}",
            f"{settings.DY_SIDECAR_PRODUCT_NAME=}",
            f"{settings.POSTGRES_SETTINGS=}",
        )
    return is_enabled
