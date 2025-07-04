from typing import Annotated

from models_library.api_schemas_catalog.services import LatestServiceGet, ServiceGetV2
from models_library.services import ServiceMetaDataPublished
from models_library.services_history import ServiceRelease
from models_library.services_regex import DYNAMIC_SERVICE_KEY_RE
from models_library.services_types import ServiceKey
from pydantic import ConfigDict, StringConstraints

from ..api_resources import compose_resource_name
from ..basic_types import VersionStr
from .base import (
    ApiServerOutputSchema,
    BaseService,
)

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

    version_display: str | None

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
                "version_display": "8.0.0",
            }
        },
    )

    @classmethod
    def create_from_image(cls, image_meta: ServiceMetaDataPublished) -> "Program":
        data = image_meta.model_dump(
            include={
                "name",
                "key",
                "version",
                "description",
                "contact",
                "version_display",
            },
        )
        return cls(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            url=None,
            version_display=data.pop("version_display"),
            **data,
        )

    @classmethod
    def create_from_service(cls, service: ServiceGetV2 | LatestServiceGet) -> "Program":
        data = service.model_dump(
            include={
                "name",
                "key",
                "version",
                "description",
                "contact",
                "version_display",
            },
        )
        return cls(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            url=None,
            version_display=data.pop("version_display"),
            **data,
        )

    @classmethod
    def create_from_service_release(
        cls,
        *,
        service_key: ServiceKey,
        description: str,
        name: str,
        service: ServiceRelease
    ) -> "Program":
        return cls(
            id=service_key,
            version=service.version,
            title=name,
            url=None,
            description=description,
            version_display=service.version,
        )

    @classmethod
    def compose_resource_name(cls, key: ProgramKeyId, version: VersionStr) -> str:
        return compose_resource_name("programs", key, "releases", version)
