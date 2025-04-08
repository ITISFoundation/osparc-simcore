import urllib.parse
from typing import Annotated

import packaging.version
from models_library.services import ServiceMetaDataPublished
from models_library.services_regex import DYNAMIC_SERVICE_KEY_RE
from packaging.version import Version
from pydantic import ConfigDict, Field, HttpUrl, StringConstraints
from simcore_service_api_server.models.schemas._utils import ApiServerOutputSchema

from ...models._utils_pydantic import UriSchema
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


class Program(ApiServerOutputSchema):
    """A released solver with a specific version"""

    id: Annotated[ProgramKeyId, Field(..., description="Program identifier")]
    version: Annotated[
        VersionStr, Field(..., description="semantic version number of the node")
    ]
    title: Annotated[
        str,
        StringConstraints(max_length=100),
        Field(..., description="Human readable name"),
    ]
    description: Annotated[
        str | None,
        StringConstraints(max_length=500),
        Field(None, description="Description of the program"),
    ]
    url: Annotated[
        HttpUrl | None, UriSchema(), Field(..., description="Link to get this resource")
    ]

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

    @property
    def pep404_version(self) -> Version:
        """Rich version type that can be used e.g. to compare"""
        return packaging.version.parse(self.version)

    @property
    def url_friendly_id(self) -> str:
        """Use to pass id as parameter in urls"""
        return urllib.parse.quote_plus(self.id)

    @property
    def resource_name(self) -> str:
        """Relative resource name"""
        return self.compose_resource_name(self.id, self.version)

    @property
    def name(self) -> str:
        """API standards notation (see api_resources.py)"""
        return self.resource_name

    @classmethod
    def compose_resource_name(
        cls, program_key: ProgramKeyId, program_version: VersionStr
    ) -> str:
        return compose_resource_name(
            "programs", program_key, "releases", program_version
        )
