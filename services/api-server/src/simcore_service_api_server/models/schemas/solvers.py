from typing import Annotated, Any, Literal, Self, TypeAlias

from models_library.api_schemas_catalog.services import (
    LatestServiceGet,
    ServiceGetV2,
    ServiceSummary,
)
from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.emails import LowerCaseEmailStr
from models_library.services import ServiceMetaDataPublished
from models_library.services_history import ServiceRelease
from models_library.services_regex import COMPUTATIONAL_SERVICE_KEY_RE
from models_library.services_types import ServiceKey
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ..api_resources import compose_resource_name
from .base import BaseService

# NOTE:
# - API does NOT impose prefix (simcore)/(services)/comp because does not know anything about registry deployed. This constraint
#   should be responsibility of the catalog. Those prefix
# - Strictly speaking solvers should be a collection and releases a sub-collection, i.e. solvers/*/releases/*
#   But, based on user feedback, everything was flattened into a released-solvers resource simply denoted "solvers"
STRICT_RELEASE_NAME_REGEX_W_CAPTURE = r"^([^\s:]+)+:([^\s:/]+)$"
STRICT_RELEASE_NAME_REGEX = r"^[^\s:]+:[0-9\.]+$"

# - API will add flexibility to identify solver resources using aliases. Analogously to docker images e.g. a/b == a/b:latest == a/b:2.3
#
SOLVER_ALIAS_REGEX = r"^([^\s:]+)+:?([^\s:/]*)$"
LATEST_VERSION = "latest"


SOLVER_RESOURCE_NAME_RE = r"^solvers/([^\s/]+)/releases/([\d\.]+)$"


SolverKeyId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=COMPUTATIONAL_SERVICE_KEY_RE)
]


class Solver(BaseService):
    """A released solver with a specific version"""

    maintainer: Annotated[str, Field(description="Maintainer of the solver")]

    version_display: Annotated[
        str | None,
        Field(description="A user-friendly or marketing name for the release."),
    ] = None

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "id": "simcore/services/comp/isolve",
                "version": "2.1.1",
                "version_display": "2.1.1-2023-10-01",
                "title": "iSolve",
                "description": "EM solver",
                "maintainer": "info@itis.swiss",
                "url": "https://api.osparc.io/v0/solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/2.1.1",
            }
        },
    )

    @classmethod
    def create_from_image(cls, image_meta: ServiceMetaDataPublished) -> Self:
        return cls(
            id=image_meta.key,
            version=image_meta.version,
            title=image_meta.name,
            description=image_meta.description,
            maintainer=image_meta.contact,
            version_display=image_meta.version_display,
            url=None,
        )

    @classmethod
    def create_from_service(
        cls, service: ServiceGetV2 | LatestServiceGet | ServiceSummary
    ) -> Self:
        # Common fields in all service types
        maintainer = ""
        if hasattr(service, "contact") and service.contact:
            maintainer = service.contact

        return cls(
            id=service.key,
            version=service.version,
            title=service.name,
            description=service.description,
            maintainer=maintainer or "UNDEFINED",
            version_display=(
                service.version_display if hasattr(service, "version_display") else None
            ),
            url=None,
        )

    @classmethod
    def create_from_service_release(
        cls,
        *,
        service_key: ServiceKey,
        description: str,
        contact: LowerCaseEmailStr | None,
        name: str,
        service: ServiceRelease
    ) -> "Solver":
        return cls(
            id=service_key,
            version=service.version,
            title=name,
            url=None,
            description=description,
            maintainer=contact or "",
        )

    @classmethod
    def compose_resource_name(cls, key: str, version: str) -> str:
        return compose_resource_name("solvers", key, "releases", version)


PortKindStr: TypeAlias = Literal["input", "output"]


class SolverPort(BaseModel):
    key: str = Field(
        ...,
        description="port identifier name",
        pattern=PUBLIC_VARIABLE_NAME_RE,
        title="Key name",
    )
    kind: PortKindStr
    content_schema: dict[str, Any] | None = Field(
        None,
        description="jsonschema for the port's value. SEE https://json-schema.org",
    )
    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "key": "input_2",
                "kind": "input",
                "content_schema": {
                    "title": "Sleep interval",
                    "type": "integer",
                    "x_unit": "second",
                    "minimum": 0,
                    "maximum": 5,
                },
            }
        },
    )
