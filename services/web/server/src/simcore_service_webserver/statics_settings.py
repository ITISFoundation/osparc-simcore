""" Configures front-end statics

    Typically dumped in statics.json
"""
from typing import Any, Optional

from aiohttp import web
from models_library.utils.change_case import snake_to_camel
from pydantic import AnyHttpUrl, Field, HttpUrl
from settings_library.base import BaseCustomSettings

from ._constants import APP_SETTINGS_KEY

OSPARC_DEPENDENCIES = [
    dict(
        name="adminer",
        version="4.8.0",
        url="https://www.adminer.org/",
        thumbnail="https://www.adminer.org/static/images/logo.png",
    ),
    dict(
        name="dask",
        version="-",
        url="https://docs.dask.org/en/latest/scheduler-overview.html",
        thumbnail="https://dask.org/_images/dask_horizontal_white_no_pad.svg",
    ),
    dict(
        name="docker",
        version="-",
        url="https://www.docker.com/",
        thumbnail="https://www.docker.com/sites/default/files/d8/2019-07/horizontal-logo-monochromatic-white.png",
    ),
    dict(
        name="github",
        version="-",
        url="https://github.com/",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Octicons-mark-github.svg/2048px-Octicons-mark-github.svg.png",
    ),
    dict(
        name="minio",
        version="-",
        url="https://min.io/",
        thumbnail="https://min.io/resources/img/logo.svg",
    ),
    dict(
        name="portainer",
        version="-",
        url="https://www.portainer.io/",
        thumbnail="https://www.portainer.io/hubfs/Brand%20Assets/Logos/Portainer%20Logo%20Solid%20All%20-%20Blue%20no%20padding.svg",
    ),
    dict(
        name="postgres",
        version="10.11",
        url="https://www.postgresql.org/",
        thumbnail="https://www.postgresql.org/media/img/about/press/elephant.png",
    ),
    dict(
        name="redis",
        version="-",
        url="https://redis.io/",
        thumbnail="https://redis.io/images/redis-white.png",
    ),
]


class FrontEndAppSettings(BaseCustomSettings):

    # urls to manuals
    WEBSERVER_MANUAL_MAIN_URL: Optional[HttpUrl] = None
    WEBSERVER_MANUAL_EXTRA_URL: Optional[HttpUrl] = None
    WEBSERVER_MANUAL_TI_URL: Optional[HttpUrl] = None  # TODO: Move this to products  db

    # extra feedback url
    WEBSERVER_FEEDBACK_FORM_URL: Optional[HttpUrl] = None

    # fogbugz
    WEBSERVER_FOGBUGZ_LOGIN_URL: Optional[HttpUrl] = None
    # NEW case url (see product overrides env_prefix = WEBSERVER_S4L_ ... )
    # SEE https://support.fogbugz.com/hc/en-us/articles/360011241594-Generating-a-Case-Template-with-bookmarklets
    # https://<your_fogbugz_URL>.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=<project-id>&ixArea=<area_id>&ixCategory=<category_id>&ixPersonAssignedTo=<assigned_user_id>&sTitle=<title_of_case>&sEvent=<body_of text>
    WEBSERVER_FOGBUGZ_NEWCASE_URL: Optional[HttpUrl] = None

    WEBSERVER_S4L_FOGBUGZ_NEWCASE_URL: Optional[
        HttpUrl
    ] = None  # TODO: Move this to products  db
    WEBSERVER_TIS_FOGBUGZ_NEWCASE_URL: Optional[
        HttpUrl
    ] = None  # TODO: Move this to products  db

    def to_statics(self) -> dict[str, Any]:
        data = self.dict(
            exclude_none=True,
            by_alias=True,
        )
        data["osparc_dependencies"] = OSPARC_DEPENDENCIES

        return {
            snake_to_camel(k.replace("WEBSERVER_", "").lower()): v
            for k, v in data.items()
        }


class StaticWebserverModuleSettings(BaseCustomSettings):
    # TODO: remove
    STATIC_WEBSERVER_ENABLED: bool = Field(
        True,
        description=(
            "if enabled it will try to fetch and cache the 3 product index webpages"
        ),
        env=["STATIC_WEBSERVER_ENABLED", "WEBSERVER_STATIC_MODULE_ENABLED"],  # legacy
    )

    # TODO: move WEBSERVER_FRONTEND here??

    # TODO: host/port
    STATIC_WEBSERVER_URL: AnyHttpUrl = Field(
        "http://static-webserver:8000",
        description="url fort static content",
        env=[
            "STATIC_WEBSERVER_URL",
            "WEBSERVER_STATIC_MODULE_STATIC_WEB_SERVER_URL",
        ],  # legacy
    )


def get_plugin_settings(app: web.Application) -> StaticWebserverModuleSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_STATICWEB
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, StaticWebserverModuleSettings)  # nosec
    return settings
