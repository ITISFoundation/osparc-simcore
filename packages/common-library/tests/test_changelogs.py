# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from packaging.version import Version
from pytest_mock import MockerFixture
from simcore_service_api_server.api.routes._constants import (
    ChangedEndpoint,
    ChangelogType,
    DeprecatedEndpoint,
    NewEndpoint,
    RemovedEndpoint,
    create_route_config,
    create_route_description,
    validate_changelog,
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


def test_changelog_entry_types():
    assert ChangelogType.NEW.value < ChangelogType.CHANGED.value
    assert ChangelogType.CHANGED.value < ChangelogType.DEPRECATED.value
    assert ChangelogType.DEPRECATED.value < ChangelogType.REMOVED.value


def test_changelog_entry_classes():
    # Test NewEndpoint
    new_entry = NewEndpoint("0.5.0")
    assert new_entry.entry_type == ChangelogType.NEW
    assert new_entry.get_version() == Version("0.5.0")
    assert "New in *version 0.5.0*" in new_entry.to_string()

    # Test ChangedEndpoint
    changed_entry = ChangedEndpoint("0.6.0", "Added authentication")
    assert changed_entry.entry_type == ChangelogType.CHANGED
    assert changed_entry.get_version() == Version("0.6.0")
    assert (
        "Changed in *version 0.6.0*: Added authentication" in changed_entry.to_string()
    )

    # Test DeprecatedEndpoint
    deprecated_entry = DeprecatedEndpoint("/v1/better-endpoint", "0.7.0")
    assert deprecated_entry.entry_type == ChangelogType.DEPRECATED
    assert deprecated_entry.get_version() == Version("0.7.0")
    assert "Deprecated" in deprecated_entry.to_string()
    assert "/v1/better-endpoint" in deprecated_entry.to_string()

    # Test RemovedEndpoint
    removed_entry = RemovedEndpoint("0.9.0", "Use the new endpoint instead")
    assert removed_entry.entry_type == ChangelogType.REMOVED
    assert removed_entry.get_version() == Version("0.9.0")
    assert "Removed in *version 0.9.0*" in removed_entry.to_string()
    assert "Use the new endpoint instead" in removed_entry.to_string()


def test_validate_changelog():
    """Test the validate_changelog function"""
    # Valid changelog
    valid_changelog = [
        NewEndpoint("0.5.0"),
        ChangedEndpoint("0.6.0", "Added authentication"),
        DeprecatedEndpoint("/v1/better-endpoint", "0.7.0"),
    ]
    validate_changelog(valid_changelog)  # Should not raise

    # Invalid order
    invalid_order = [
        NewEndpoint("0.5.0"),
        DeprecatedEndpoint("/v1/better-endpoint", "0.7.0"),
        ChangedEndpoint("0.6.0", "Added authentication"),  # Wrong order
    ]
    with pytest.raises(ValueError, match="order"):
        validate_changelog(invalid_order)

    # Missing NEW as first entry
    missing_new = [
        ChangedEndpoint("0.6.0", "Added authentication"),
        DeprecatedEndpoint("/v1/better-endpoint", "0.7.0"),
    ]
    with pytest.raises(ValueError, match="First changelog entry must be NEW"):
        validate_changelog(missing_new)

    # Multiple DEPRECATED entries
    multiple_deprecated = [
        NewEndpoint("0.5.0"),
        DeprecatedEndpoint("/v1/better-endpoint", "0.7.0"),
        DeprecatedEndpoint("/v1/another-endpoint", "0.8.0"),
    ]
    with pytest.raises(ValueError, match="Only one DEPRECATED entry"):
        validate_changelog(multiple_deprecated)


def test_create_route_description():
    """Test the create_route_description function"""
    # Basic description
    base_desc = "This is a test endpoint"
    changelog = [
        NewEndpoint("0.5.0"),
        ChangedEndpoint("0.6.0", "Added authentication"),
    ]

    desc = create_route_description(base=base_desc, changelog=changelog)

    assert base_desc in desc
    assert "New in *version 0.5.0*" in desc
    assert "Changed in *version 0.6.0*: Added authentication" in desc


def test_create_route_config_for_deprecated_endpoints() -> None:
    """Test route configuration for deprecated endpoints"""
    alternative_route = "/v1/new-endpoint"
    changelog = [
        NewEndpoint("0.5.0"),
        DeprecatedEndpoint(alternative_route),
    ]

    config = create_route_config(
        base_description="This is a deprecated endpoint",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": True,
        "description": create_route_description(
            base="This is a deprecated endpoint",
            changelog=changelog,
        ),
    }

    assert config == expected_config


def test_create_route_config_for_to_be_released_endpoints(
    mock_api_version: str,
) -> None:
    """Test route configuration for endpoints that will be released in future versions"""
    future_version = f"{int(Version(mock_api_version).major) + 1}.0.0"
    changelog = [
        NewEndpoint(future_version),
    ]

    config = create_route_config(
        base_description=f"This is a feature coming in version {future_version}",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": False,
        "include_in_schema": False,
        "description": create_route_description(
            base=f"This is a feature coming in version {future_version}",
            changelog=changelog,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_removal_notice() -> None:
    """Test route configuration with explicit removal notice in changelog"""
    removal_message = "Use the new endpoint instead"
    alternative_route = "/v1/better-endpoint"

    changelog = [
        NewEndpoint("0.5.0"),
        DeprecatedEndpoint(alternative_route),
        RemovedEndpoint("0.9.0", removal_message),
    ]

    config = create_route_config(
        base_description="This endpoint will be removed in version 0.9.0",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": True,
        "description": create_route_description(
            base="This endpoint will be removed in version 0.9.0",
            changelog=changelog,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_regular_endpoint() -> None:
    """Test route configuration for a standard endpoint (not deprecated, not upcoming)"""
    changelog = [NewEndpoint("0.5.0")]

    config = create_route_config(
        base_description="This is a standard endpoint",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": False,
        "include_in_schema": True,
        "description": create_route_description(
            base="This is a standard endpoint",
            changelog=changelog,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_mixed_changelog() -> None:
    """Test route configuration with a complex changelog containing multiple entries"""
    alternative_route = "/v1/better-endpoint"
    changelog = [
        NewEndpoint("0.5.0"),
        ChangedEndpoint("0.6.0", "Added authentication"),
        DeprecatedEndpoint(alternative_route),
        RemovedEndpoint("0.9.0", "Use the new endpoint instead"),
    ]

    config = create_route_config(
        base_description="This endpoint has a complex history",
        changelog=changelog,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": True,
        "description": create_route_description(
            base="This endpoint has a complex history",
            changelog=changelog,
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
        "include_in_schema": True,
        "description": create_route_description(
            base="This endpoint has no changelog",
            changelog=[],
        ),
    }

    assert config == expected_config
