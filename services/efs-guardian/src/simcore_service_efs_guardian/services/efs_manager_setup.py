import logging
from collections.abc import AsyncIterator
from typing import cast

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager, State
from settings_library.efs import AwsEfsSettings
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    stop_after_delay,
    wait_random_exponential,
)

from ..exceptions.custom_errors import ApplicationSetupError
from .efs_manager import EfsManager

_logger = logging.getLogger(__name__)


def configure_efs_manager(app_lifespan: LifespanManager[FastAPI]) -> None:
    async def _efs_manager_lifespan(app: FastAPI) -> AsyncIterator[State]:
        aws_efs_settings: AwsEfsSettings = app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS

        app.state.efs_manager = None
        app.state.efs_manager = efs_manager = await EfsManager.create(
            app,
            aws_efs_settings.EFS_MOUNTED_PATH,
            aws_efs_settings.EFS_PROJECT_SPECIFIC_DATA_DIRECTORY,
        )

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(_logger, logging.WARNING),
        ):
            with attempt:
                await efs_manager.initialize_directories()
        yield {}

    app_lifespan.add(_efs_manager_lifespan)


def get_efs_manager(app: FastAPI) -> EfsManager:
    if not app.state.efs_manager:
        raise ApplicationSetupError(msg="Efs Manager is not available. Please check the configuration.")
    return cast(EfsManager, app.state.efs_manager)
