from datetime import timedelta
from typing import Annotated, Final

from aiohttp import web
from common_library.pydantic_validators import validate_numeric_string_as_timedelta
from pydantic import ByteSize, Field, HttpUrl, TypeAdapter, field_validator
from pydantic_settings import SettingsConfigDict
from settings_library.base import BaseCustomSettings

from ..application_keys import APP_SETTINGS_APPKEY

_DEFAULT_THUMBNAIL: Final[HttpUrl] = TypeAdapter(HttpUrl).validate_python("https://via.placeholder.com/170x120.png")


class StudiesDispatcherSettings(BaseCustomSettings):
    STUDIES_ACCESS_ANONYMOUS_ALLOWED: Annotated[
        bool,
        Field(description="If enabled, the study links are accessible to anonymous users"),
    ] = False

    STUDIES_GUEST_ACCOUNT_LIFETIME: Annotated[
        timedelta,
        Field(description="Sets lifetime of a guest user until it is logged out and removed by the GC"),
    ] = timedelta(minutes=15)

    STUDIES_DEFAULT_SERVICE_THUMBNAIL: Annotated[
        HttpUrl,
        Field(description="Default thumbnail for services or dispatch project with a service"),
    ] = _DEFAULT_THUMBNAIL

    STUDIES_DEFAULT_FILE_THUMBNAIL: Annotated[
        HttpUrl,
        Field(description="Default thumbnail for dispatch projects with only data (i.e. file-picker)"),
    ] = _DEFAULT_THUMBNAIL

    STUDIES_MAX_FILE_SIZE_ALLOWED: Annotated[
        ByteSize,
        Field(
            description="Limits the size of the files that can be dispatched. "
            "Note that the accuracy of the file size is not guaranteed and this limit might be surpassed"
        ),
    ] = TypeAdapter(ByteSize).validate_python("50Mib")

    @field_validator("STUDIES_GUEST_ACCOUNT_LIFETIME")
    @classmethod
    def _is_positive_lifetime(cls, v):
        if v and isinstance(v, timedelta) and v.total_seconds() <= 0:
            msg = f"Must be a positive lifetime, got {v.total_seconds()=}"
            raise ValueError(msg)
        return v

    _validate_studies_guest_account_lifetime = validate_numeric_string_as_timedelta("STUDIES_GUEST_ACCOUNT_LIFETIME")

    model_config = SettingsConfigDict(
        json_schema_extra={
            "example": {
                "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",  # 2 days 1h and 10 mins
                "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
            },
        }
    )

    def is_login_required(self):
        """Used just to allow protecting the dispatcher redirect entrypoint programmatically
        Normally dispatcher entrypoints are opened
        """
        return not self.STUDIES_ACCESS_ANONYMOUS_ALLOWED


def get_plugin_settings(app: web.Application) -> StudiesDispatcherSettings:
    settings = app[APP_SETTINGS_APPKEY].WEBSERVER_STUDIES_DISPATCHER
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, StudiesDispatcherSettings)  # nosec
    return settings
