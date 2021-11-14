from pkg_resources import parse_version
from pydantic import BaseModel


def bump_version_string(current_version: str, bump: str) -> str:
    """
    BUMP means to increment the version number to a new, unique value
    NOTE: Simple implementation of version-bump w/o extra dependencies
    """
    version = parse_version(current_version)

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


class VersionInfo(BaseModel):
    executable_name: str
    executable_version: str
    service_version: str
    service_integration: str
