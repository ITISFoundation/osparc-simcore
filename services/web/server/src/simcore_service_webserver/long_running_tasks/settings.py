from typing import Annotated

from aiohttp import web
from pydantic import Field
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY


class LongRunningTasksSettings(BaseCustomSettings):
    LONG_RUNNING_TASKS_NAMESPACE_SUFFIX: Annotated[
        str,
        Field(
            description=(
                "suffix to distinguish between the various services based on this image "
                "inside the long_running_tasks framework"
            ),
        ),
    ]


def get_plugin_settings(app: web.Application) -> LongRunningTasksSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_LONG_RUNNING_TASKS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, LongRunningTasksSettings)  # nosec
    return settings
