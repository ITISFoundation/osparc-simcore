# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from common_library.changelog import (
    ChangedEndpoint,
    ChangelogType,
    DeprecatedEndpoint,
    NewEndpoint,
    RetiredEndpoint,
    create_route_config,
    create_route_description,
    validate_changelog,
)
from packaging.version import Version
from pytest_mock import MockerFixture


@pytest.fixture
def current_api_version(mocker: MockerFixture) -> str:
    """Fixture to mock the API_VERSION for testing purposes"""
    return "0.7.0"


def test_changelog_entry_types():
    assert ChangelogType.NEW.value < ChangelogType.CHANGED.value
    assert ChangelogType.CHANGED.value < ChangelogType.DEPRECATED.value
    assert ChangelogType.DEPRECATED.value < ChangelogType.RETIRED.value


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
    assert "in *version 0.7.0*" in deprecated_entry.to_string()
    assert "/v1/better-endpoint" in deprecated_entry.to_string()

    # Test DeprecatedEndpoint without version
    deprecated_no_version = DeprecatedEndpoint("/v1/better-endpoint")
    assert "Deprecated" in deprecated_no_version.to_string()
    assert "in *version" not in deprecated_no_version.to_string()

    # Test RetiredEndpoint
    removed_entry = RetiredEndpoint("0.9.0", "Use the new endpoint instead")
    assert removed_entry.entry_type == ChangelogType.RETIRED
    assert removed_entry.get_version() == Version("0.9.0")
    assert "Retired in *version 0.9.0*" in removed_entry.to_string()
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


def test_create_route_config_for_deprecated_endpoints(current_api_version: str) -> None:
    """Test route configuration for deprecated endpoints"""
    alternative_route = "/v1/new-endpoint"
    changelog = [
        NewEndpoint("0.5.0"),
        DeprecatedEndpoint(alternative_route),
    ]

    config = create_route_config(
        base_description="This is a deprecated endpoint",
        changelog=changelog,
        current_version=Version(current_api_version),
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
    current_api_version: str,
) -> None:
    """Test route configuration for endpoints that will be released in future versions"""
    future_version = f"{int(Version(current_api_version).major) + 1}.0.0"
    changelog = [
        NewEndpoint(future_version),
    ]

    config = create_route_config(
        base_description=f"This is a feature coming in version {future_version}",
        changelog=changelog,
        current_version=Version(current_api_version),
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


def test_create_route_config_with_removal_notice(current_api_version: str) -> None:
    """Test route configuration with explicit removal notice in changelog"""
    removal_message = "Use the new endpoint instead"
    alternative_route = "/v1/better-endpoint"

    changelog = [
        NewEndpoint("0.5.0"),
        DeprecatedEndpoint(alternative_route),
        RetiredEndpoint("0.9.0", removal_message),
    ]

    config = create_route_config(
        base_description="This endpoint will be removed in version 0.9.0",
        changelog=changelog,
        current_version=current_api_version,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": False,  # Changed from True to False due to REMOVED entry
        "description": create_route_description(
            base="This endpoint will be removed in version 0.9.0",
            changelog=changelog,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_regular_endpoint(current_api_version: str) -> None:
    """Test route configuration for a standard endpoint (not deprecated, not upcoming)"""
    changelog = [NewEndpoint("0.5.0")]

    config = create_route_config(
        base_description="This is a standard endpoint",
        changelog=changelog,
        current_version=current_api_version,
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


def test_create_route_config_with_mixed_changelog(current_api_version: str) -> None:

    alternative_route = "/v1/better-endpoint"
    changelog = [
        NewEndpoint("0.5.0"),
        ChangedEndpoint("0.6.0", "Added authentication"),
        ChangedEndpoint("0.6.2", "Fixed a bug"),
        DeprecatedEndpoint(alternative_route),
        RetiredEndpoint("0.9.0", "Use the new endpoint instead"),
    ]

    config = create_route_config(
        base_description="This endpoint has a complex history",
        changelog=changelog,
        current_version=current_api_version,
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": False,  # Changed from True to False due to REMOVED entry
        "description": create_route_description(
            base="This endpoint has a complex history",
            changelog=changelog,
        ),
    }

    assert config == expected_config


def test_create_route_config_with_empty_changelog(current_api_version: str) -> None:

    config = create_route_config(
        base_description="This endpoint has no changelog",
        current_version=current_api_version,
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


# Add a new test to explicitly verify the version display in deprecated endpoints
def test_deprecated_endpoint_with_version():
    """Test that DeprecatedEndpoint correctly displays the version information when available"""
    # With version
    deprecated_with_version = DeprecatedEndpoint("/new/endpoint", "0.8.0")
    assert "in *version 0.8.0*" in deprecated_with_version.to_string()

    # Without version
    deprecated_without_version = DeprecatedEndpoint("/new/endpoint")
    assert "in *version" not in deprecated_without_version.to_string()
