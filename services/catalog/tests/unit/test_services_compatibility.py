# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import arrow
import pytest
from models_library.services_types import ServiceVersion
from models_library.users import UserID
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pytest_mock import MockerFixture, MockType
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.models.services_db import ReleaseFromDB
from simcore_service_catalog.services.compatibility import (
    _get_latest_compatible_version,
    evaluate_service_compatibility_map,
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


def _create_as(cls, **overrides):
    kwargs = {
        "compatibility_policy": None,
        "created": arrow.now().datetime,
        "deprecated": None,
        "version_display": None,
    }
    kwargs.update(overrides)
    return cls(**kwargs)


@pytest.fixture
def mock_repo(mocker: MockerFixture) -> MockType:
    return mocker.AsyncMock(ServicesRepository)


async def test_evaluate_service_compatibility_map_with_default_policy(
    mock_repo: MockType, user_id: UserID
):
    service_release_history = [
        _create_as(ReleaseFromDB, version="1.0.0"),
        _create_as(ReleaseFromDB, version="1.0.1"),
        _create_as(ReleaseFromDB, version="1.1.0"),
        _create_as(ReleaseFromDB, version="2.0.0"),
    ]

    compatibility_map = await evaluate_service_compatibility_map(
        mock_repo, "product_name", user_id, service_release_history
    )

    assert len(compatibility_map) == 4
    assert compatibility_map[ServiceVersion("1.0.0")].can_update_to.version == "1.0.1"
    assert compatibility_map[ServiceVersion("1.0.1")] is None
    assert compatibility_map[ServiceVersion("1.1.0")] is None
    assert compatibility_map[ServiceVersion("2.0.0")] is None


async def test_evaluate_service_compatibility_map_with_custom_policy(
    mock_repo: MockType, user_id: UserID
):
    service_release_history = [
        _create_as(ReleaseFromDB, version="1.0.0"),
        _create_as(
            ReleaseFromDB,
            version="1.0.1",
            compatibility_policy={"versions_specifier": ">1.1.0,<=2.0.0"},
        ),
        _create_as(ReleaseFromDB, version="1.2.0"),
        _create_as(ReleaseFromDB, version="2.0.0"),
    ]

    compatibility_map = await evaluate_service_compatibility_map(
        mock_repo, "product_name", user_id, service_release_history
    )

    assert len(compatibility_map) == 4
    assert (
        compatibility_map[ServiceVersion("1.0.0")].can_update_to.version == "1.0.1"
    )  # default
    assert (
        compatibility_map[ServiceVersion("1.0.1")].can_update_to.version == "2.0.0"
    )  # version customized
    assert compatibility_map[ServiceVersion("1.2.0")] is None
    assert compatibility_map[ServiceVersion("2.0.0")] is None


async def test_evaluate_service_compatibility_map_with_other_service(
    mock_repo: MockType, user_id: UserID
):
    service_release_history = [
        _create_as(ReleaseFromDB, version="1.0.0"),
        _create_as(
            ReleaseFromDB,
            version="1.0.1",
            compatibility_policy={
                "other_service_key": "simcore/services/comp/other_service",
                "versions_specifier": "<=5.1.0",
            },
        ),
    ]

    mock_repo.get_service_history.return_value = [
        _create_as(ReleaseFromDB, version="5.0.0"),
        _create_as(ReleaseFromDB, version="5.1.0"),
        _create_as(ReleaseFromDB, version="5.2.0"),
    ]

    compatibility_map = await evaluate_service_compatibility_map(
        mock_repo, "product_name", user_id, service_release_history
    )

    assert len(compatibility_map) == 2
    assert compatibility_map[ServiceVersion("1.0.0")].can_update_to.version == "1.0.1"
    # NOTE: 1.0.1 is also upgradable but it is not evaluated as so because our algorithm only
    # checks comptatibility once instead of recursively

    assert (
        compatibility_map[ServiceVersion("1.0.1")].can_update_to.key
        == "simcore/services/comp/other_service"
    )
    assert compatibility_map[ServiceVersion("1.0.1")].can_update_to.version == "5.1.0"


async def test_evaluate_service_compatibility_map_with_deprecated_versions(
    mock_repo: MockType, user_id: UserID
):
    service_release_history = [
        _create_as(ReleaseFromDB, version="1.0.0"),
        _create_as(ReleaseFromDB, version="1.0.1", deprecated=arrow.now().datetime),
        _create_as(ReleaseFromDB, version="1.2.0"),
        _create_as(ReleaseFromDB, version="1.2.5"),
    ]

    compatibility_map = await evaluate_service_compatibility_map(
        mock_repo, "product_name", user_id, service_release_history
    )

    assert len(compatibility_map) == 4
    assert (
        compatibility_map[ServiceVersion("1.0.0")] is None
    )  # cannot upgrade to deprecated 1.0.1
    assert compatibility_map[ServiceVersion("1.0.1")] is None  # Deprecated version
    assert compatibility_map[ServiceVersion("1.2.0")].can_update_to.version == "1.2.5"
    assert compatibility_map[ServiceVersion("1.2.5")] is None
