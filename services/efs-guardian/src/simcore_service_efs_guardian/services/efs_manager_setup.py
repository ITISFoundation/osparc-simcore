import logging
from typing import cast

from fastapi import FastAPI
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


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        aws_efs_settings: AwsEfsSettings = (
            app.state.settings.EFS_GUARDIAN_AWS_EFS_SETTINGS
        )

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

    async def on_shutdown() -> None:
        if app.state.efs_manager:
            ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_efs_manager(app: FastAPI) -> EfsManager:
    if not app.state.efs_manager:
        raise ApplicationSetupError(
            msg="Efs Manager is not available. Please check the configuration."
        )
    return cast(EfsManager, app.state.efs_manager)
