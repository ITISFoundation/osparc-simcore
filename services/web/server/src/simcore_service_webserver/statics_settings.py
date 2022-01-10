""" Configures front-end statics

    Typically dumped in statics.json
"""
from typing import Dict, List, Optional

from pydantic import AnyHttpUrl, BaseModel, BaseSettings, Field, HttpUrl

from .utils import snake_to_camel

APP_CLIENTAPPS_SETTINGS_KEY = f"{__file__}.client_apps_settings"


# these are the apps built right now by web/client
FRONTEND_APPS_AVAILABLE = frozenset({"osparc", "tis", "s4l"})
FRONTEND_APP_DEFAULT = "osparc"

assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE


class OsparcDependency(BaseModel):
    name: str
    version: str
    url: AnyHttpUrl
    thumbnail: Optional[AnyHttpUrl] = None


def discover_osparc_dependencies() -> List[OsparcDependency]:
    return [
        OsparcDependency(
            name="adminer",
            version="4.8.0",
            url="https://www.adminer.org/",
            thumbnail="https://www.adminer.org/static/images/logo.png",
        ),
        OsparcDependency(
            name="celery",
            version="-",
            url="https://docs.celeryproject.org/en/stable/",
            thumbnail="https://www.fullstackpython.com/img/logos/celery.png",
        ),
        OsparcDependency(
            name="dask",
            version="-",
            url="https://docs.dask.org/en/latest/scheduler-overview.html",
            thumbnail="https://dask.org/_images/dask_horizontal_white_no_pad.svg",
        ),
        OsparcDependency(
            name="docker",
            version="-",
            url="https://www.docker.com/",
            thumbnail="https://www.docker.com/sites/default/files/d8/2019-07/horizontal-logo-monochromatic-white.png",
        ),
        OsparcDependency(
            name="github",
            version="-",
            url="https://github.com/",
            thumbnail="https://upload.wikimedia.org/wikipedia/commons/thumb/9/91/Octicons-mark-github.svg/2048px-Octicons-mark-github.svg.png",
        ),
        OsparcDependency(
            name="minio",
            version="-",
            url="https://min.io/",
            thumbnail="https://min.io/resources/img/logo.svg",
        ),
        OsparcDependency(
            name="portainer",
            version="-",
            url="https://www.portainer.io/",
            thumbnail="https://www.portainer.io/hubfs/Brand%20Assets/Logos/Portainer%20Logo%20Solid%20All%20-%20Blue%20no%20padding.svg",
        ),
        OsparcDependency(
            name="postgres",
            version="10.11",
            url="https://www.postgresql.org/",
            thumbnail="https://www.postgresql.org/media/img/about/press/elephant.png",
        ),
        OsparcDependency(
            name="redis",
            version="-",
            url="https://redis.io/",
            thumbnail="https://redis.io/images/redis-white.png",
        ),
    ]


class FrontEndAppSettings(BaseSettings):

    # urls to manuals
    manual_main_url: Optional[HttpUrl] = None
    manual_extra_url: Optional[HttpUrl] = None

    # extra feedback url
    feedback_form_url: Optional[HttpUrl] = None

    # fogbugz
    fogbugz_login_url: Optional[HttpUrl] = None
    # NEW case url (see product overrides env_prefix = WEBSERVER_S4L_ ... )
    # SEE https://support.fogbugz.com/hc/en-us/articles/360011241594-Generating-a-Case-Template-with-bookmarklets
    # https://<your_fogbugz_URL>.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=<project-id>&ixArea=<area_id>&ixCategory=<category_id>&ixPersonAssignedTo=<assigned_user_id>&sTitle=<title_of_case>&sEvent=<body_of text>
    fogbugz_newcase_url: Optional[HttpUrl] = None
    s4l_fogbugz_newcase_url: Optional[HttpUrl] = None
    tis_fogbugz_newcase_url: Optional[HttpUrl] = None

    osparc_dependencies: List[OsparcDependency] = Field(
        default_factory=discover_osparc_dependencies
    )

    class Config:
        case_sensitive = False
        alias_generator = snake_to_camel
        env_prefix = "WEBSERVER_"

    # ---

    def to_statics(self) -> Dict:
        return self.dict(
            exclude_none=True,
            by_alias=True,
        )


class StaticWebserverModuleSettings(BaseSettings):
    enabled: bool = Field(
        True,
        description=(
            "if enabled it will try to fetch and cache the 3 product index webpages"
        ),
    )

    static_web_server_url: AnyHttpUrl = Field(
        "http://static-webserver:8000", description="url fort static content"
    )

    class Config:
        case_sensitive = False
        env_prefix = "WEBSERVER_STATIC_MODULE_"
