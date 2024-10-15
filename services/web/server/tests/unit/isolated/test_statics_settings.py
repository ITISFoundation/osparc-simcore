# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json

from pydantic import AnyHttpUrl, BaseModel, TypeAdapter
from simcore_service_webserver.statics.settings import (
    _THIRD_PARTY_REFERENCES,
    FrontEndAppSettings,
    StaticWebserverModuleSettings,
)

FOGBUGZ_NEWCASE_URL_TEMPLATE = r"https://z43.manuscript.com/f/cases/new?command=new&pg=pgEditBug&ixProject={project}&ixArea={area}"
# NEW case url (see product overrides env_prefix = WEBSERVER_S4L_ ... )
# SEE https://support.fogbugz.com/hc/en-us/articles/360011241594-Generating-a-Case-Template-with-bookmarklets
# https://<your_fogbugz_URL>.fogbugz.com/f/cases/new?command=new&pg=pgEditBug&ixProject=<project-id>&ixArea=<area_id>&ixCategory=<category_id>&ixPersonAssignedTo=<assigned_user_id>&sTitle=<title_of_case>&sEvent=<body_of text>
class OsparcDependency(BaseModel):
    name: str
    version: str
    url: AnyHttpUrl
    thumbnail: AnyHttpUrl | None = None


def test_valid_osparc_dependencies():
    deps = TypeAdapter(list[OsparcDependency]).validate_python(_THIRD_PARTY_REFERENCES)
    assert deps


def test_frontend_app_settings(mock_env_devel_environment: dict[str, str]):

    settings = FrontEndAppSettings.create_from_envs()
    assert settings

    # is json-serializable
    statics = settings.to_statics()
    assert json.dumps(statics)

    TypeAdapter(list[OsparcDependency]).validate_python(statics["thirdPartyReferences"])


def test_static_webserver_module_settings(mock_env_devel_environment: dict[str, str]):
    settings = StaticWebserverModuleSettings.create_from_envs()
    assert settings
