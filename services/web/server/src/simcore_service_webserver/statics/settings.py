""" Configures front-end statics

    Typically dumped in statics.json
"""
from typing import Any

import pycountry
from aiohttp import web
from models_library.utils.change_case import snake_to_camel
from pydantic import AliasChoices, AnyHttpUrl, Field, TypeAdapter
from settings_library.base import BaseCustomSettings
from typing_extensions import (  # https://docs.pydantic.dev/latest/api/standard_library_types/#typeddict
    TypedDict,
)

from .._constants import APP_SETTINGS_KEY


class ThirdPartyInfoDict(TypedDict):
    name: str
    version: str
    url: str
    thumbnail: str


_THIRD_PARTY_REFERENCES = [
    ThirdPartyInfoDict(
        name="adminer",
        version="4.8.1",
        url="https://www.adminer.org/",
        thumbnail="https://www.adminer.org/static/images/logo.png",
    ),
    ThirdPartyInfoDict(
        name="dask",
        version="-",
        url="https://docs.dask.org/en/latest/scheduler-overview.html",
        thumbnail="https://docs.dask.org/en/stable/_static/images/dask-horizontal-white.svg",
    ),
    ThirdPartyInfoDict(
        name="docker",
        version="-",
        url="https://www.docker.com/",
        thumbnail="https://upload.wikimedia.org/wikipedia/en/thumb/f/f4/Docker_logo.svg/120px-Docker_logo.svg.png",
    ),
    ThirdPartyInfoDict(
        name="github",
        version="-",
        url="https://github.com/",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Octicons-mark-github.svg/2048px-Octicons-mark-github.svg.png",
    ),
    ThirdPartyInfoDict(
        name="minio",
        version="-",
        url="https://min.io/",
        thumbnail="https://min.io/resources/img/logo.svg",
    ),
    ThirdPartyInfoDict(
        name="portainer",
        version="-",
        url="https://www.portainer.io/",
        thumbnail="https://www.portainer.io/hubfs/Brand%20Assets/Logos/Portainer%20Logo%20Solid%20All%20-%20Blue%20no%20padding.svg",
    ),
    ThirdPartyInfoDict(
        name="postgres",
        version="10.11",
        url="https://www.postgresql.org/",
        thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/2/29/Postgresql_elephant.svg/120px-Postgresql_elephant.svg.png",
    ),
    ThirdPartyInfoDict(
        name="redis",
        version="-",
        url="https://redis.io/",
        thumbnail="https://upload.wikimedia.org/wikipedia/en/thumb/6/6b/Redis_Logo.svg/200px-Redis_Logo.svg.png",
    ),
]


# NOTE: syncs info on countries with UI


class CountryInfoDict(TypedDict):
    name: str
    alpha2: str


class FrontEndInfoDict(TypedDict, total=True):
    third_party_references: list[ThirdPartyInfoDict]
    countries: list[CountryInfoDict]


class FrontEndAppSettings(BaseCustomSettings):
    """
    Any settings to be transmitted to the front-end via statics goes here
    """

    # NOTE: for the moment, None but left here for future use

    def to_statics(self) -> dict[str, Any]:
        data = self.model_dump(
            exclude_none=True,
            by_alias=True,
        )
        data.update(
            FrontEndInfoDict(
                third_party_references=_THIRD_PARTY_REFERENCES,
                countries=sorted(
                    (
                        CountryInfoDict(
                            name=c.name,
                            alpha2=c.alpha_2,
                        )
                        for c in pycountry.countries
                    ),
                    key=lambda i: i["name"],
                ),
            ),
        )

        return {
            snake_to_camel(k.replace("WEBSERVER_", "").lower()): v
            for k, v in data.items()
        }


class StaticWebserverModuleSettings(BaseCustomSettings):
    STATIC_WEBSERVER_URL: AnyHttpUrl = Field(
        default=TypeAdapter(AnyHttpUrl).validate_python("http://static-webserver:8000"),
        description="url fort static content",
        validation_alias=AliasChoices(
            "STATIC_WEBSERVER_URL",
            "WEBSERVER_STATIC_MODULE_STATIC_WEB_SERVER_URL",  # legacy
        ),
    )


def get_plugin_settings(app: web.Application) -> StaticWebserverModuleSettings:
    settings = app[APP_SETTINGS_KEY].WEBSERVER_STATICWEB
    assert settings, "setup_settings not called?"  # nosec
    assert isinstance(settings, StaticWebserverModuleSettings)  # nosec
    return settings
