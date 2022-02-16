from aiohttp import web
from pydantic.fields import Field
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class StudiesAccessSettings(BaseCustomSettings):
    STUDIES_ACCESS_ANONYMOUS_ALLOWED: bool = Field(
        False,
        description="If enabled, the study links are accessible to anonymous users",
        env=["STUDIES_ACCESS_ANONYMOUS_ALLOWED", "WEBSERVER_STUDIES_ACCESS_ENABLED"],
    )

    @property
    def is_login_required(self):
        return not self.STUDIES_ACCESS_ANONYMOUS_ALLOWED


def get_plugin_settings(app: web.Application) -> StudiesAccessSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_STUDIES_ACCESS
    assert settings, "setup_settings not called?"  # nosec
    return settings
