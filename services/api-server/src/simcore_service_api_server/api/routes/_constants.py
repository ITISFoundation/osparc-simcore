from typing import Any, Final

#
# CHANGELOG formatted-messages for API routes
#
# - Append at the bottom of the route's description
# - These are displayed in the swagger doc
# - These are displayed in client's doc as well (auto-generator)
# - Inspired on this idea https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#describing-changes-between-versions
#

# newly created endpoint in given version
FMSG_CHANGELOG_NEW_IN_VERSION: Final[str] = "New in *version {}*\n"

# changes in given version with message
FMSG_CHANGELOG_CHANGED_IN_VERSION: Final[str] = "Changed in *version {}*: {}\n"

# marked as deprecated and will be removed in given version
FMSG_CHANGELOG_REMOVED_IN_VERSION: Final[str] = "Removed in *version {}*: {}\n"

FMSG_CHANGELOG_DEPRECATED: Final[str] = (
    "🚨 **Deprecated**: This endpoint is deprecated and will be removed in a future release.\n"
    "Please use `{}` instead.\n\n"
)

DEFAULT_MAX_STRING_LENGTH: Final[int] = 500


def create_route_description(
    *,
    base: str = "",
    deprecated: bool = False,
    alternative: str | None = None,  # alternative route to use
    changelog: list[str] | None = None,
) -> str:
    """
    Builds a consistent route description with optional deprecation and changelog information.

    Args:
        base (str): Main route description.
        deprecated (tuple): (retirement_date, alternative_route) if deprecated.
        changelog (List[str]): List of formatted changelog strings.

    Returns:
        str: Final description string.
    """
    parts = []

    if deprecated:
        assert alternative, "If deprecated, alternative must be provided"  # nosec
        parts.append(FMSG_CHANGELOG_DEPRECATED.format(alternative))

    if base:
        parts.append(base)

    if changelog:
        parts.append("\n".join(changelog))

    return "\n\n".join(parts)


def create_route_config(
    base_description: str = "",
    *,
    to_be_released_in: str | None = None,
    to_be_removed_in: str | None = None,
    alternative: str | None = None,
    changelog: list[str] | None = None,
) -> dict[str, Any]:
    """
    Creates route configuration options including description.

    Args:
        base_description: Main route description
        to_be_released_in: Version where this route will be released (for upcoming features)
        to_be_removed_in: Version where this route will be removed (for deprecated endpoints)
        alternative: Alternative route to use (required if to_be_removed_in is provided)
        changelog: List of formatted changelog strings

    Returns:
        dict: Route configuration options that can be used as kwargs for route decorators
    """
    route_options: dict[str, Any] = {}

    # Build changelog
    if changelog is None:
        changelog = []

    if to_be_released_in:
        # Add version information to the changelog if not already there
        version_note = FMSG_CHANGELOG_NEW_IN_VERSION.format(to_be_released_in)
        if not any(version_note in item for item in changelog):
            changelog.append(version_note)
        # Hide from schema until released
        route_options["include_in_schema"] = False

    if to_be_removed_in:
        # Require an alternative route if this endpoint will be removed
        assert (  # nosec
            alternative
        ), "If to_be_removed_in is provided, alternative must be provided"  # nosec

        # Add removal notice to the changelog if not already there
        removal_message = (
            "This endpoint is deprecated and will be removed in a future version"
        )
        removal_note = FMSG_CHANGELOG_REMOVED_IN_VERSION.format(
            to_be_removed_in, removal_message
        )
        if not any(removal_note in item for item in changelog):
            changelog.append(removal_note)

        # Mark as deprecated
        route_options["deprecated"] = True

    # Create description
    route_options["description"] = create_route_description(
        base=base_description,
        deprecated=bool(to_be_removed_in),
        alternative=alternative,
        changelog=changelog,
    )

    return route_options
