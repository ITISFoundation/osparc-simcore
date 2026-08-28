import logging

from fastapi import FastAPI
from models_library.service_settings_labels import UserPreferencesVersionSource
from models_library.services_types import ServiceVersion
from pydantic import TypeAdapter, ValidationError

from ...core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)


def get_resolved_version(app: FastAPI) -> ServiceVersion | None:
    settings: ApplicationSettings = app.state.settings

    if settings.DY_SIDECAR_USER_PREFERENCES_VERSION_SOURCE == UserPreferencesVersionSource.SERVICE_VERSION_IDENTIFIER:
        return settings.DY_SIDECAR_SERVICE_VERSION

    # NOTE: version_display is free text and not guaranteed to be a valid ServiceVersion;
    # disable the feature rather than fail if it cannot be used to namespace preferences
    try:
        return TypeAdapter(ServiceVersion).validate_python(settings.DY_SIDECAR_SERVICE_VERSION_DISPLAY)
    except ValidationError:
        _logger.warning(
            "version_display=%r is not a valid ServiceVersion; disabling user services preferences",
            settings.DY_SIDECAR_SERVICE_VERSION_DISPLAY,
        )
        return None


def is_feature_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    resolved_version = get_resolved_version(app)

    is_enabled = (
        settings.DY_SIDECAR_SERVICE_KEY is not None
        and settings.DY_SIDECAR_SERVICE_VERSION is not None
        and settings.DY_SIDECAR_USER_PREFERENCES_PATH is not None
        and settings.DY_SIDECAR_PRODUCT_NAME is not None
        and settings.POSTGRES_SETTINGS is not None
        and resolved_version is not None
    )
    if not is_enabled:
        _logger.warning(
            "user services preferences manager is not enabled: %s, %s, %s, %s, %s, %s",
            f"{settings.DY_SIDECAR_SERVICE_KEY=}",
            f"{settings.DY_SIDECAR_SERVICE_VERSION=}",
            f"{settings.DY_SIDECAR_USER_PREFERENCES_PATH=}",
            f"{settings.DY_SIDECAR_PRODUCT_NAME=}",
            f"{settings.POSTGRES_SETTINGS=}",
            f"{resolved_version=}",
        )
    return is_enabled
