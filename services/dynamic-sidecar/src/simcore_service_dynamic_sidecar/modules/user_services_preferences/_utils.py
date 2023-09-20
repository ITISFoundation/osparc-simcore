from fastapi import FastAPI

from ...core.settings import ApplicationSettings


def is_feature_enabled(app: FastAPI) -> bool:
    settings: ApplicationSettings = app.state.settings
    return (
        settings.DY_SIDECAR_SERVICE_KEY is not None
        and settings.DY_SIDECAR_SERVICE_VERSION is not None
        and settings.DY_SIDECAR_USER_PREFERENCES_PATH is not None
    )
