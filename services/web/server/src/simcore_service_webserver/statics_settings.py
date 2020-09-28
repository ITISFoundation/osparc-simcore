""" Configures front-end statics

    Typically dumped in statics.json
"""

from typing import Dict

from pydantic import BaseSettings

from .utils import snake_to_camel

APP_CLIENTAPPS_SETTINGS_KEY = f"{__file__}.client_apps_settings"


# these are the apps built right now by web/client

class FrontEndApp(str, Enum):
    osparc = "osparc"
    s4l = "s4l"
    tis = "tis"

FRONTEND_APPS_AVAILABLE = frozenset([e.value for e in FrontEndApp])
FRONTEND_APP_DEFAULT = FrontEndApp.osparc.value



class _CommonConfig:
    case_sensitive = False
    alias_generator = snake_to_camel


class ClientAppSettings(BaseSettings):

    # urls to manuals
    manual_main_url: Optional[HttpUrl] = None
    manual_extra_url: Optional[HttpUrl] = None

    # fogbugz tickets
    # SEE https://support.fogbugz.com/hc/en-us/articles/360011241594-Generating-a-Case-Template-with-bookmarklets
    # https://<your_fogbugz_URL>.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=<project-id>&ixArea=<area_id>&ixCategory=<category_id>&ixPersonAssignedTo=<assigned_user_id>&sTitle=<title_of_case>&sEvent=<body_of text>
    fogbugz_url: Optional[HttpUrl] = None

    # extra feedback url
    feedback_form_url: Optional[HttpUrl] = None

    class Config(_CommonConfig):
        env_prefix = "WEBSERVER_"

    # ---

    def to_client_statics(self) -> Dict:
        return self.dict(
            exclude_none=True,
            by_alias=True,
        )


class S4LAppSettings(ClientAppSettings):
    """ Overrides default settings for s4l client app"""

    fogbugz_url: HttpUrl = "https://z43.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=45&ixArea=458"

    class Config(_CommonConfig):
        env_prefix = "WEBSERVER_S4L_"


class TiSAppSettings(ClientAppSettings):
    """ Overrides default settings for tis client app"""

    fogbugz_url: HttpUrl = "https://z43.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=45&ixArea=459"

    class Config(_CommonConfig):
        env_prefix = "WEBSERVER_TIS_"
