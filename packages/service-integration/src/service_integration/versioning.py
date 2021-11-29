from datetime import datetime

from packaging.version import Version
from pydantic import BaseModel
from pydantic.fields import Field
from pydantic.types import constr

from .basic_regex import SEMANTIC_VERSION_RE

# TODO: create https://pydantic-docs.helpmanual.io/usage/types/#custom-data-types for packaging.version.Version
# We needdefine __modify_schema__ (see how is done with UUID in pydantic) and a validator that
# allows parsing from string as well
#
VersionStr = constr(regex=SEMANTIC_VERSION_RE)


def bump_version_string(current_version: str, bump: str) -> str:
    """
    BUMP means to increment the version number to a new, unique value
    NOTE: Simple implementation of version-bump w/o extra dependencies
    """
    version = Version(current_version)

    # CAN ONLY bump releases not pre/post/dev releases
    if version.is_devrelease or version.is_postrelease or version.is_prerelease:
        raise NotImplementedError("Can only bump released versions")

    major, minor, patch = version.major, version.minor, version.micro
    if bump == "major":
        new_version = f"{major+1}.0.0"
    elif bump == "minor":
        new_version = f"{major}.{minor+1}.0"
    else:
        new_version = f"{major}.{minor}.{patch+1}"
    return new_version


# TODO: from https://github.com/ITISFoundation/osparc-simcore/issues/2409
# ### versioning
# a single version number does not suffice. Instead we should have a set of versions that describes "what is inside the container"
# - service version (following semantic versioning): for the published service
# - service integration version: sidecar
# - executable name: the public name of the wrapped program (e.g. matlab)
# - executable version: the version of the program (e.g. matlab 2020b)
# - further libraries version dump (e.g. requirements.txt, etc)


class ExecutableVersionInfo(BaseModel):
    display_name: str
    display_version: str
    description: str
    name: str
    version: VersionStr
    released: datetime

    class Config:
        schema_extra = {
            "example": {
                "display_name": "SEMCAD X",
                "display_version": "Matterhorn Student Edition 1",
                "description": "z43 flag simulator for student use",
                "name": "semcad-x",
                "version": "3.4.5-beta",
                "released": "2021-11-19T14:58:45.900979",
            }
        }


class ServiceVersionInfo(BaseModel):
    version: VersionStr
    integration_version: VersionStr = Field(
        ..., description="osparc internal integration version"
    )
    released: datetime = Field(..., description="Publication/release date")

    class Config:
        schema_extra = {
            "example": {
                "version": "1.0.0",  # e.g. first time released as an osparc
                "integration_version": "2.1.0",
                "released": "2021-11-19T14:58:45.900979",
            }
        }
