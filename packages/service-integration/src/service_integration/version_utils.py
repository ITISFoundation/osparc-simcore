"""
    Simple implementation of version utils
"""
from pkg_resources import parse_version


def bump_version_string(current_version: str, bump: str) -> str:
    """ BUMP means to increment the version number to a new, unique value """
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
