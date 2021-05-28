""" Configures front-end statics

    Typically dumped in statics.json
"""
from typing import Dict, Optional

from pydantic import AnyHttpUrl, BaseSettings, Field, HttpUrl

from .utils import snake_to_camel

APP_CLIENTAPPS_SETTINGS_KEY = f"{__file__}.client_apps_settings"


# these are the apps built right now by web/client
FRONTEND_APPS_AVAILABLE = frozenset({"osparc", "tis", "s4l"})
FRONTEND_APP_DEFAULT = "osparc"

assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE


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
