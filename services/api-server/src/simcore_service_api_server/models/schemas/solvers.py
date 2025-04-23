from typing import Annotated, Any, Literal

from models_library.api_schemas_catalog.services import LatestServiceGet, ServiceGetV2
from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.services import ServiceMetaDataPublished
from models_library.services_regex import COMPUTATIONAL_SERVICE_KEY_RE
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from ...models.schemas._base import BaseService
from ..api_resources import compose_resource_name

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


# SOLVER ----------
#
SOLVER_RESOURCE_NAME_RE = r"^solvers/([^\s/]+)/releases/([\d\.]+)$"


SolverKeyId = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=COMPUTATIONAL_SERVICE_KEY_RE)
]


class Solver(BaseService):
    """A released solver with a specific version"""

    maintainer: str = Field(..., description="Maintainer of the solver")

    model_config = ConfigDict(
        extra="ignore",
        json_schema_extra={
            "example": {
                "id": "simcore/services/comp/isolve",
                "version": "2.1.1",
                "title": "iSolve",
                "description": "EM solver",
                "maintainer": "info@itis.swiss",
                "url": "https://api.osparc.io/v0/solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/2.1.1",
            }
        },
    )

    @classmethod
    def create_from_image(cls, image_meta: ServiceMetaDataPublished) -> "Solver":
        data = image_meta.model_dump(
            include={"name", "key", "version", "description", "contact"},
        )
        return cls(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            maintainer=data.pop("contact"),
            url=None,
            **data,
        )

    @classmethod
    def create_from_service(cls, service: ServiceGetV2 | LatestServiceGet) -> "Solver":
        data = service.model_dump(
            include={"name", "key", "version", "description", "contact"},
        )
        return cls(
            id=data.pop("key"),
            version=data.pop("version"),
            title=data.pop("name"),
            url=None,
            maintainer=data.pop("contact"),
            **data,
        )

    @classmethod
    def compose_resource_name(cls, key: str, version: str) -> str:
        return compose_resource_name("solvers", key, "releases", version)


PortKindStr = Literal["input", "output"]


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
