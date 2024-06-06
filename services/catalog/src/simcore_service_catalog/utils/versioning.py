# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import TypeAlias

import packaging.version
from packaging.version import Version

_VersionOrStr: TypeAlias = Version | str


def as_version(v: _VersionOrStr) -> Version:
    return packaging.version.Version(v) if isinstance(v, str) else v


def is_patch_release(version: _VersionOrStr, reference: _VersionOrStr) -> bool:
    """Returns True if version is a patch release from reference"""
    v: Version = as_version(version)
    r: Version = as_version(reference)
    return v.major == r.major and v.minor == r.minor and r.micro < v.micro  # type: ignore
