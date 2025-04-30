# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture
from simcore_service_api_server.api.routes._constants import (
    FMSG_CHANGELOG_CHANGED_IN_VERSION,
    FMSG_CHANGELOG_DEPRECATED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    FMSG_CHANGELOG_REMOVED_IN_VERSION,
    create_route_config,
    create_route_description,
)


@pytest.fixture
def mock_api_version(mocker: MockerFixture) -> str:
    """Fixture to mock the API_VERSION for testing purposes"""
    import simcore_service_api_server.api.routes._constants

    mock_version = "0.7.0"
    mocker.patch.object(
        simcore_service_api_server.api.routes._constants,
        "API_VERSION",
        mock_version,
    )
    return mock_version


def test_create_route_config_for_deprecated_endpoints() -> None:
    """Test route configuration for deprecated endpoints"""
    alternative_route = "/v1/new-endpoint"
    changelog = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
        FMSG_CHANGELOG_DEPRECATED_IN_VERSION.format("0.6", alternative_route),
    ]

    config = create_route_config(
        base_description="This is a deprecated endpoint",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": False,
        "description": create_route_description(
            base="This is a deprecated endpoint",
            changelog=changelog,
            deprecated_in="Unknown",
            alternative=alternative_route,
        ),
    }

    assert config == expected_config


def test_create_route_config_for_to_be_released_endpoints(
    mock_api_version: str,
) -> None:
    """Test route configuration for endpoints that will be released in future versions"""
    future_version = str(Version(mock_api_version).major + 1)
    changelog = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format(future_version),
    ]

    config = create_route_config(
        base_description=f"This is a feature coming in version {future_version}",
        changelog=changelog,
    )

    expected_config = {
        "include_in_schema": True,  # Note: This is inverted from previous behavior
        "deprecated": False,
        "description": create_route_description(
            base=f"This is a feature coming in version {future_version}",
            changelog=changelog,
            deprecated_in=None,
            alternative=None,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_removal_notice() -> None:
    """Test route configuration with explicit removal notice in changelog"""
    removal_message = (
        "This endpoint is deprecated and will be removed in a future version"
    )
    removal_note = FMSG_CHANGELOG_REMOVED_IN_VERSION.format("0.9", removal_message)
    alternative_route = "/v1/better-endpoint"

    changelog = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
        FMSG_CHANGELOG_DEPRECATED_IN_VERSION.format(alternative_route),
        removal_note,
    ]

    config = create_route_config(
        base_description="This endpoint will be removed in version 0.9",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": False,
        "description": create_route_description(
            base="This endpoint will be removed in version 0.9",
            changelog=changelog,
            deprecated_in="Unknown",
            alternative=alternative_route,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_regular_endpoint() -> None:
    """Test route configuration for a standard endpoint (not deprecated, not upcoming)"""
    changelog = [FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5")]

    config = create_route_config(
        base_description="This is a standard endpoint",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": False,
        "include_in_schema": False,
        "description": create_route_description(
            base="This is a standard endpoint",
            changelog=changelog,
            deprecated_in=None,
            alternative=None,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_mixed_changelog() -> None:
    """Test route configuration with a complex changelog containing multiple entries"""
    alternative_route = "/v1/better-endpoint"
    changelog = [
        FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
        FMSG_CHANGELOG_CHANGED_IN_VERSION.format("0.6", "Added authentication"),
        FMSG_CHANGELOG_DEPRECATED_IN_VERSION.format(alternative_route),
        FMSG_CHANGELOG_REMOVED_IN_VERSION.format("0.9", "Use the new endpoint instead"),
    ]

    config = create_route_config(
        base_description="This endpoint has a complex history",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": False,
        "description": create_route_description(
            base="This endpoint has a complex history",
            changelog=changelog,
            deprecated_in="Unknown",
            alternative=alternative_route,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_empty_changelog() -> None:
    """Test route configuration with an empty changelog"""
    config = create_route_config(
        base_description="This endpoint has no changelog",
    )

    expected_config = {
        "deprecated": False,
        "include_in_schema": False,
        "description": create_route_description(
            base="This endpoint has no changelog",
            changelog=[],
            deprecated_in=None,
            alternative=None,
        ),
    }

    assert config == expected_config
