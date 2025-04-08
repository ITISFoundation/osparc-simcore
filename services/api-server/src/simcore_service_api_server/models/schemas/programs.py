from typing import Annotated

from models_library.services import ServiceMetaDataPublished
from models_library.services_regex import DYNAMIC_SERVICE_KEY_RE
from pydantic import ConfigDict, StringConstraints
from simcore_service_api_server.models.schemas._base import (
    ApiServerOutputSchema,
    BaseService,
)

from ..api_resources import compose_resource_name
from ..basic_types import VersionStr

# - API will add flexibility to identify solver resources using aliases. Analogously to docker images e.g. a/b == a/b:latest == a/b:2.3
#
LATEST_VERSION = "latest"


# SOLVER ----------
#
PROGRAM_RESOURCE_NAME_RE = r"^programs/([^\s/]+)/releases/([\d\.]+)$"


ProgramKeyId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=DYNAMIC_SERVICE_KEY_RE)
]


class Program(BaseService, ApiServerOutputSchema):
    """A released program with a specific version"""

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "id": "simcore/services/dynamic/sim4life",
                "version": "8.0.0",
                "title": "Sim4life",
                "description": "Simulation framework",
                "maintainer": "info@itis.swiss",
                "url": "https://api.osparc.io/v0/solvers/simcore%2Fservices%2Fdynamic%2Fsim4life/releases/8.0.0",
            }
        },
    )

    @classmethod
    def create_from_image(cls, image_meta: ServiceMetaDataPublished) -> "Program":
        data = image_meta.model_dump(
            include={"name", "key", "version", "description", "contact"},
        )
        return cls(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            url=None,
            **data,
        )

    @classmethod
    def compose_resource_name(cls, key: ProgramKeyId, version: VersionStr) -> str:
        return compose_resource_name("programs", key, "releases", version)
