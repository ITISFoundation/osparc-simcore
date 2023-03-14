from datetime import datetime, timedelta, timezone

from aiohttp import web
from pydantic import validator
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

    @validator("STUDIES_GUEST_ACCOUNT_LIFETIME")
    @classmethod
    def is_positive_lifetime(cls, v):
        if v and isinstance(v, timedelta):
            if v.total_seconds() <= 0:
                raise ValueError("Must be a positive lifetime")
        return v

    def is_login_required(self):
        return not self.STUDIES_ACCESS_ANONYMOUS_ALLOWED

    def get_guest_expiration(self) -> datetime:
        """Value assigned to user.expires_at"""
        return datetime.now(timezone.utc) + self.STUDIES_GUEST_ACCOUNT_LIFETIME

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
