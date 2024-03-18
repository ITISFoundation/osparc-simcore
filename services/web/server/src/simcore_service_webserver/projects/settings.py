from datetime import timedelta

from aiohttp import web
from pydantic import ByteSize, Field, NonNegativeInt, parse_obj_as
from settings_library.base import BaseCustomSettings

from .._constants import APP_SETTINGS_KEY


class ProjectsSettings(BaseCustomSettings):
    PROJECTS_MAX_COPY_SIZE_BYTES: ByteSize = Field(
        parse_obj_as(ByteSize, "30Gib"),
        description="defines the maximum authorized project data size"
        " when copying a project (disable with 0)",
    )
    PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES: NonNegativeInt = Field(
        default=5,
        description="defines the number of dynamic services in a project that can be started concurrently (a value of 0 will disable it)",
    )

    PROJECTS_INACTIVITY_INTERVAL: timedelta = Field(
        timedelta(seconds=20),
        description="interval after which services need to be idle in order to be considered inactive",
    )


def get_plugin_settings(app: web.Application) -> ProjectsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ProjectsSettings)  # nosec
    return settings
