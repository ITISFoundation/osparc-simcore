# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from simcore_service_catalog.services.compatibility import (
    _get_latest_compatible_version,
)

# References
#
# - Semantic versioning:
# 	- https://semver.org/
# - Python Packaging User Guide:
# 	- https://packaging.python.org/en/latest/specifications/version-specifiers/#version-specifiers
# - `packaging` library
#   - https://packaging.pypa.io/en/stable/version.html
#   - https://packaging.pypa.io/en/stable/specifiers.html
#


def test_compatible_with_minor_release():
    """Testing https://packaging.python.org/en/latest/specifications/version-specifiers/#compatible-release

    The following groups of version clauses are equivalent:
    ~= 2.2
    >= 2.2, == 2.*
    """
    minor_compatible_spec = SpecifierSet("~=2.2")

    assert "2.2" in minor_compatible_spec
    assert "2.2.0" in minor_compatible_spec

    assert Version("2.2") == Version("2.2.0")

    # bigger patch -> compatible
    assert "2.2.1" in minor_compatible_spec

    # bigger minor -> compatible
    assert "2.3" in minor_compatible_spec

    # bigger major -> INcompatible
    assert "3.3" not in minor_compatible_spec

    # smaller major -> INcompatible
    assert "2.1" not in minor_compatible_spec
    assert "1.0" not in minor_compatible_spec
    assert "0.1.5" not in minor_compatible_spec


def test_compatible_with_patch_release():
    """Testing https://packaging.python.org/en/latest/specifications/version-specifiers/#compatible-release

    The following groups of version clauses are equivalent:
    ~= 1.4.5
    >= 1.4.5, == 1.4.*
    """
    patch_compatible_spec = SpecifierSet("~=1.4.5")

    assert "1.4.5" in patch_compatible_spec

    # bigger patch -> compatible
    assert "1.4.6" in patch_compatible_spec

    # smaller patch -> INcompatible
    assert "1.4.4" not in patch_compatible_spec

    # bigger minor -> INcompatible!
    assert "1.5" not in patch_compatible_spec
    assert "1.5.1" not in patch_compatible_spec

    # smaller major -> INcompatible
    assert "0.1.5" not in patch_compatible_spec
    assert "1.0" not in patch_compatible_spec
    assert "1.1" not in patch_compatible_spec
    assert "1.3" not in patch_compatible_spec


@pytest.fixture
def versions_history() -> list[Version]:
    return sorted(
        Version(f"{M}.{m}.{p}")
        for M in range(10)
        for m in range(0, 5, 2)
        for p in range(0, 10, 4)
    )


def test_version_specifiers(versions_history: list[Version]):
    # given a list of versions, test the first compatibilty starting from the latest
    # If i have ">1.2.23,~=1.2.23"

    version = Version("1.2.3")

    # >1.2.3
    newer_version_spec = SpecifierSet(f">{version}")

    # >= 1.2, == 1.*
    minor_compatible_spec = SpecifierSet(f"~={version.major}.{version.minor}")

    # >= 1.2.3, == 1.2.*
    patch_compatible_spec = SpecifierSet(
        f"~={version.major}.{version.minor}.{version.micro}"
    )

    compatible = list(
        (minor_compatible_spec & newer_version_spec).filter(versions_history)
    )
    assert version not in compatible
    assert all(v > version for v in compatible)
    assert all(v.major == version.major for v in compatible)

    latest_compatible = compatible[-1]
    assert version < latest_compatible

    compatible = list(
        (patch_compatible_spec & newer_version_spec).filter(versions_history)
    )
    assert version not in compatible
    assert all(v > version for v in compatible)
    assert all(
        v.major == version.major and v.minor == version.minor for v in compatible
    )
    latest_compatible = compatible[-1]
    assert version < latest_compatible


def test_get_latest_compatible_version(versions_history: list[Version]):
    latest_first_releases = sorted(versions_history, reverse=True)

    # cannot upgrde to anything
    latest = latest_first_releases[0]
    assert _get_latest_compatible_version(latest, latest_first_releases) is None

    # bump MAJOR
    not_released = Version(f"{latest.major+1}")
    assert _get_latest_compatible_version(not_released, latest_first_releases) is None

    # decrease patch
    target = Version(f"{latest.major}.{latest.minor}.{latest.micro-1}")
    assert _get_latest_compatible_version(target, latest_first_releases) == latest

    # decrease minor (with default compatibility specs)
    target = Version(f"{latest.major}.{latest.minor-2}.0")
    latest_compatible = _get_latest_compatible_version(target, latest_first_releases)
    assert latest_compatible
    assert latest_compatible < latest
