""" Configures front-end statics

    Typically dumped in statics.json
"""
from typing import Any

from aiohttp import web
from models_library.utils.change_case import snake_to_camel
from pydantic import AnyHttpUrl, Field
from settings_library.base import BaseCustomSettings

from ._constants import APP_SETTINGS_KEY

THIRD_PARTY_REFERENCES = [
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
        thumbnail="https://docs.dask.org/en/stable/_static/images/dask-horizontal-white.svg",
    ),
    dict(
        name="docker",
        version="-",
        url="https://www.docker.com/",
        thumbnail="https://upload.wikimedia.org/wikipedia/en/thumb/f/f4/Docker_logo.svg/120px-Docker_logo.svg.png",
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
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Postgresql_elephant.svg/120px-Postgresql_elephant.svg.png",
    ),
    dict(
        name="redis",
        version="-",
        url="https://redis.io/",
        thumbnail="https://upload.wikimedia.org/wikipedia/en/thumb/6/6b/Redis_Logo.svg/200px-Redis_Logo.svg.png",
    ),
]


class FrontEndAppSettings(BaseCustomSettings):
    """
    Any settings to be transmitted to the front-end via statics goes here
    """

    # NOTE: for the moment, None but left here for future use

    def to_statics(self) -> dict[str, Any]:
        data = self.dict(
            exclude_none=True,
            by_alias=True,
        )
        data["third_party_references"] = THIRD_PARTY_REFERENCES

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
