from datetime import timedelta

from aiohttp import web
from pydantic import HttpUrl, validator
from pydantic.fields import Field
from servicelib.aiohttp.application_keys import APP_SETTINGS_KEY
from settings_library.base import BaseCustomSettings


class StudiesDispatcherSettings(BaseCustomSettings):
    STUDIES_ACCESS_ANONYMOUS_ALLOWED: bool = Field(
        False,
        description="If enabled, the study links are accessible to anonymous users",
        env=["STUDIES_ACCESS_ANONYMOUS_ALLOWED", "WEBSERVER_STUDIES_ACCESS_ENABLED"],
    )

    STUDIES_GUEST_ACCOUNT_LIFETIME: timedelta = Field(
        default=timedelta(minutes=15),
        description="Sets lifetime of a guest user until it is logged out "
        " and removed by the GC",
    )

    STUDIES_DEFAULT_SERVICE_THUMBNAIL: HttpUrl = Field(
        default="https://via.placeholder.com/170x120.png",
        description="Default servcie thumbnails in the service response",
    )

    @validator("STUDIES_GUEST_ACCOUNT_LIFETIME")
    @classmethod
    def is_positive_lifetime(cls, v):
        if v and isinstance(v, timedelta) and v.total_seconds() <= 0:
            raise ValueError(f"Must be a positive number, got {v.total_seconds()=}")
        return v

    def is_login_required(self):
        """Returns False if study access entrypoint does not require auth

        NOTE: in special cases this entrypoing can be programatically protected with auth
        """
        return not self.STUDIES_ACCESS_ANONYMOUS_ALLOWED

    class Config:
        schema_extra = {
            "example": {
                "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",  # 2 days 1h and 10 mins
                "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
            },
        }


def get_plugin_settings(app: web.Application) -> StudiesDispatcherSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_STUDIES_DISPATCHER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, StudiesDispatcherSettings)  # nosec
    return settings
