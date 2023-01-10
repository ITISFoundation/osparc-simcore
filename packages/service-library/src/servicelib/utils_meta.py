"""  Utilities for _meta

"""
from contextlib import suppress
from typing import NamedTuple

from packaging.version import Version
from pkg_resources import Distribution


class VersionFlavoursTuple(NamedTuple):
    API_VERSION: str
    VERSION: Version
    API_TAG: str


def get_version_flavours(distribution: Distribution) -> VersionFlavoursTuple:
    version = Version(distribution.version)
    return VersionFlavoursTuple(distribution.version, version, f"v{version.major}")


def get_summary(distribution: Distribution) -> str:
    with suppress(Exception):
        try:
            metadata = distribution.get_metadata_lines("METADATA")
        except FileNotFoundError:
            metadata = distribution.get_metadata_lines("PKG-INFO")

        return next(x.split(":") for x in metadata if x.startswith("Summary:"))[-1]
    return ""
