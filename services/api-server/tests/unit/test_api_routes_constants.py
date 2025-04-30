from simcore_service_api_server.api.routes._constants import (
    FMSG_CHANGELOG_CHANGED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    FMSG_CHANGELOG_REMOVED_IN_VERSION,
    create_route_config,
    create_route_description,
)


def test_create_route_config_for_deprecated_endpoints():
    """Test route configuration for endpoints that will be removed in future versions"""
    removal_message = (
        "This endpoint is deprecated and will be removed in a future version"
    )
    config = create_route_config(
        base_description="This is a deprecated endpoint",
        to_be_removed_in="0.9",
        alternative="/v1/new-endpoint",
        changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5")],
    )

    expected_config = {
        "deprecated": True,
        "description": create_route_description(
            base="This is a deprecated endpoint",
            deprecated=True,
            alternative="/v1/new-endpoint",
            changelog=[
                FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5"),
                FMSG_CHANGELOG_REMOVED_IN_VERSION.format("0.9", removal_message),
            ],
        ),
    }

    assert config == expected_config


def test_create_route_config_for_to_be_released_endpoints():
    """Test route configuration for endpoints that will be released in future versions"""
    config = create_route_config(
        base_description="This is a feature coming in version 0.8",
        to_be_released_in="0.8",
        changelog=[FMSG_CHANGELOG_CHANGED_IN_VERSION.format("0.8", "New parameters")],
    )

    expected_config = {
        "include_in_schema": False,
        "description": create_route_description(
            base="This is a feature coming in version 0.8",
            deprecated=False,
            alternative=None,
            changelog=[
                FMSG_CHANGELOG_CHANGED_IN_VERSION.format("0.8", "New parameters"),
                FMSG_CHANGELOG_NEW_IN_VERSION.format("0.8"),
            ],
        ),
    }

    assert config == expected_config


def test_create_route_config_with_already_present_removal_notice():
    """Test that removal notice is not duplicated in changelog if already present"""
    removal_message = (
        "This endpoint is deprecated and will be removed in a future version"
    )
    removal_note = FMSG_CHANGELOG_REMOVED_IN_VERSION.format("0.9", removal_message)

    config = create_route_config(
        base_description="This endpoint will be removed in version 0.9",
        to_be_removed_in="0.9",
        alternative="/v1/better-endpoint",
        changelog=[removal_note],
    )

    expected_config = {
        "deprecated": True,
        "description": create_route_description(
            base="This endpoint will be removed in version 0.9",
            deprecated=True,
            alternative="/v1/better-endpoint",
            changelog=[removal_note],
        ),
    }

    assert config == expected_config


def test_create_route_config_with_regular_endpoint():
    """Test route configuration for a standard endpoint (not deprecated, not upcoming)"""
    config = create_route_config(
        base_description="This is a standard endpoint",
        changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5")],
    )

    expected_config = {
        "description": create_route_description(
            base="This is a standard endpoint",
            deprecated=False,
            alternative=None,
            changelog=[FMSG_CHANGELOG_NEW_IN_VERSION.format("0.5")],
        ),
    }

    assert config == expected_config


def test_create_route_config_both_pending_release_and_pending_removal():
    """Test that a route can't logically be both unreleased and deprecated at the same time"""
    # This is a somewhat illogical case, but we should handle it gracefully
    removal_message = (
        "This endpoint is deprecated and will be removed in a future version"
    )

    config = create_route_config(
        base_description="This endpoint has a confused state",
        to_be_released_in="0.10",
        to_be_removed_in="0.11",
        alternative="/v1/better-endpoint",
    )

    expected_config = {
        "deprecated": True,
        "include_in_schema": False,
        "description": create_route_description(
            base="This endpoint has a confused state",
            deprecated=True,
            alternative="/v1/better-endpoint",
            changelog=[
                FMSG_CHANGELOG_NEW_IN_VERSION.format("0.10"),
                FMSG_CHANGELOG_REMOVED_IN_VERSION.format("0.11", removal_message),
            ],
        ),
    }

    assert config == expected_config
