# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Union

import packaging.version
from packaging.version import Version

_VersionT = Union[Version, str]


def as_version(v: _VersionT) -> Version:
    return packaging.version.Version(v) if isinstance(v, str) else v  # type: ignore


def is_patch_release(version: _VersionT, reference: _VersionT) -> bool:
    """Returns True if version is a patch release from reference"""
    v: Version = as_version(version)
    r: Version = as_version(reference)
    return v.major == r.major and v.minor == r.minor and r.micro < v.micro
