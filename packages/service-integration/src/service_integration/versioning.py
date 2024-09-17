from datetime import datetime
from typing import Annotated, TypeAlias

from models_library.basic_regex import SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS
from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SemanticVersionStr: TypeAlias = Annotated[
    str, StringConstraints(pattern=SEMANTIC_VERSION_RE_W_CAPTURE_GROUPS)
]


def bump_version_string(current_version: str, bump: str) -> str:
    """
    BUMP means to increment the version number to a new, unique value
    NOTE: Simple implementation of version-bump w/o extra dependencies
    """
    version = Version(current_version)

    # CAN ONLY bump releases not pre/post/dev releases
    if version.is_devrelease or version.is_postrelease or version.is_prerelease:
        msg = "Can only bump released versions"
        raise NotImplementedError(msg)

    major, minor, patch = version.major, version.minor, version.micro
    if bump == "major":
        new_version = f"{major+1}.0.0"
    elif bump == "minor":
        new_version = f"{major}.{minor+1}.0"
    else:
        new_version = f"{major}.{minor}.{patch+1}"
    return new_version


# ### versioning
# a single version number does not suffice. Instead we should have a set of versions that describes "what is inside the container"
# - service version (following semantic versioning): for the published service
# - service integration version: sidecar
# - executable name: the public name of the wrapped program (e.g. matlab)
# - executable version: the version of the program (e.g. matlab 2020b)
# - further libraries version dump (e.g. requirements.txt, etc)
# SEE from https://github.com/ITISFoundation/osparc-simcore/issues/2409


class ExecutableVersionInfo(BaseModel):
    display_name: str
    display_version: str
    description: str
    name: str
    version: SemanticVersionStr
    released: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "display_name": "SEMCAD X",
                "display_version": "Matterhorn Student Edition 1",
                "description": "z43 flag simulator for student use",
                "name": "semcad-x",
                "version": "3.4.5-beta",
                "released": "2021-11-19T14:58:45.900979",
            }
        }
    )


class ServiceVersionInfo(BaseModel):
    version: SemanticVersionStr
    integration_version: SemanticVersionStr = Field(
        ..., description="osparc internal integration version"
    )
    released: datetime = Field(..., description="Publication/release date")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "version": "1.0.0",  # e.g. first time released as an osparc
                "integration_version": "2.1.0",
                "released": "2021-11-19T14:58:45.900979",
            }
        }
    )
