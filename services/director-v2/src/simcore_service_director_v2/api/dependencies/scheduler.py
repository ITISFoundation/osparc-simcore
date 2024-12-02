from typing import Annotated

from fastapi import Depends, FastAPI

from ...core.settings import ComputationalBackendSettings
from . import get_app


def get_scheduler_settings(
    app: Annotated[FastAPI, Depends(get_app)]
) -> ComputationalBackendSettings:
    settings: ComputationalBackendSettings = (
        app.state.settings.DIRECTOR_V2_COMPUTATIONAL_BACKEND
    )
    return settings
