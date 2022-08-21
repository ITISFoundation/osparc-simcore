from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, parse_obj_as
from simcore_service_webserver.statics_settings import OSPARC_DEPENDENCIES


def test_valid_osparc_dependencies():
    class OsparcDependency(BaseModel):
        name: str
        version: str
        url: AnyHttpUrl
        thumbnail: Optional[AnyHttpUrl] = None

    deps = parse_obj_as(list[OsparcDependency], OSPARC_DEPENDENCIES)
    assert deps
