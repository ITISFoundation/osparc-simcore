from datetime import timedelta

from aiohttp import web
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, NonNegativeInt, parse_obj_as
from settings_library.base import BaseCustomSettings

from .._constants import APP_SETTINGS_KEY


class ProjectsSettings(BaseCustomSettings):
    PROJECTS_MAX_COPY_SIZE_BYTES: ByteSize = Field(
        default=parse_obj_as(ByteSize, "30Gib"),
        description="defines the maximum authorized project data size"
        " when copying a project (disable with 0)",
    )
    PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES: NonNegativeInt = Field(
        default=5,
        description="defines the number of dynamic services in a project that can be started concurrently (a value of 0 will disable it)",
    )

    PROJECTS_INACTIVITY_INTERVAL: timedelta = Field(
        default=timedelta(seconds=20),
        description="interval after which services need to be idle in order to be considered inactive",
    )

    _validate_projects_inactivity_interval = validate_numeric_string_as_timedelta(
        "PROJECTS_INACTIVITY_INTERVAL"
    )
    PROJECTS_TRASH_RETENTION_DAYS: NonNegativeInt = Field(
        default=7, description="Trashed items will be deleted after this time"
    )


def get_plugin_settings(app: web.Application) -> ProjectsSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_PROJECTS
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, ProjectsSettings)  # nosec
    return settings
