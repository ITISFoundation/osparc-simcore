import urllib.parse
from typing import Optional, Union

import packaging.version
from models_library.basic_regex import VERSION_RE
from models_library.services import COMPUTATIONAL_SERVICE_KEY_RE, ServiceDockerData
from packaging.version import LegacyVersion, Version
from pydantic import BaseModel, Extra, Field, HttpUrl, constr

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

VersionStr = constr(strip_whitespace=True, regex=VERSION_RE)
SolverKeyId = constr(
    strip_whitespace=True,
    regex=COMPUTATIONAL_SERVICE_KEY_RE,
    # TODO: should we use here a less restrictive regex that does not impose simcore/comp/?? this should be catalog responsibility
)


class Solver(BaseModel):
    """ A released solver with a specific version """

    id: SolverKeyId = Field(
        ...,
        description="Solver identifier",
    )
    version: VersionStr = Field(
        ...,
        description="semantic version number of the node",
    )

    # Human readables Identifiers
    title: str = Field(..., description="Human readable name")
    description: Optional[str]
    maintainer: str
    # TODO: consider released: Optional[datetime]  # TODO: turn into required
    # TODO: consider version_aliases: List[str] = []  # remaining tags

    # Get links to other resources
    url: Optional[HttpUrl] = Field(..., description="Link to get this resource")

    class Config:
        extra = Extra.ignore
        schema_extra = {
            "example": {
                "id": "simcore/services/comp/isolve",
                "version": "2.1.1",
                "title": "iSolve",
                "description": "EM solver",
                "maintainer": "info@itis.swiss",
                "url": "https://api.osparc.io/v0/solvers/simcore%2Fservices%2Fcomp%2Fisolve/releases/2.1.1",
            }
        }

    @classmethod
    def create_from_image(cls, image_meta: ServiceDockerData) -> "Solver":
        data = image_meta.dict(
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

    @property
    def pep404_version(self) -> Union[Version, LegacyVersion]:
        """ Rich version type that can be used e.g. to compare """
        return packaging.version.parse(self.version)

    @property
    def url_friendly_id(self) -> str:
        """ Use to pass id as parameter in urls """
        return urllib.parse.quote_plus(self.id)

    @property
    def name(self) -> str:
        """ Resource name """
        return self.compose_resource_name(self.id, self.version)

    @classmethod
    def compose_resource_name(cls, solver_key, solver_version) -> str:
        # TODO: test sync with paths??
        return compose_resource_name("solvers", solver_key, "releases", solver_version)
