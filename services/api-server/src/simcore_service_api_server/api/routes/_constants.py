from contextlib import suppress
from typing import Any, Final

from packaging.version import Version

from ..._meta import API_VERSION

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

# marked as deprecated
FMSG_CHANGELOG_DEPRECATED_IN_VERSION: Final[str] = (
    "🚨 **Deprecated**: This endpoint is deprecated and will be removed in a future release.\n"
    "Please use `{}` instead.\n\n"
)

# marked as deprecated and will be removed in given version
FMSG_CHANGELOG_REMOVED_IN_VERSION: Final[str] = "Removed in *version {}*: {}\n"


DEFAULT_MAX_STRING_LENGTH: Final[int] = 500


def create_route_description(
    *,
    base: str = "",
    changelog: list[str] | None = None,
    deprecated_in: str | None = None,
    alternative: str | None = None,
) -> str:
    """
    Builds a consistent route description with optional deprecation and changelog information.

    Args:
        base (str): Main route description.
        changelog (list[str]): List of formatted changelog strings.
        deprecated_in (str, optional): Version when this endpoint was deprecated.
        alternative (str, optional): Alternative route to use if deprecated.

    Returns:
        str: Final description string.
    """
    parts = []

    if deprecated_in and alternative:
        parts.append(FMSG_CHANGELOG_DEPRECATED_IN_VERSION.format(alternative))

    if base:
        parts.append(base)

    if changelog:
        parts.append("\n".join(changelog))

    return "\n\n".join(parts)


def create_route_config(
    base_description: str = "",
    *,
    changelog: list[str] | None = None,
) -> dict[str, Any]:
    """
    Creates route configuration options including description based on changelog history.

    The function analyzes the changelog to determine if the endpoint:
    - Is not yet released (if the earliest entry is in a future version)
    - Is deprecated (if there's a removal notice in the changelog)

    Args:
        base_description: Main route description
        changelog: List of formatted changelog strings indicating version history

    Returns:
        dict: Route configuration options that can be used as kwargs for route decorators
    """
    route_options: dict[str, Any] = {}
    changelog = changelog or []

    # Parse changelog to determine endpoint state
    is_deprecated = False
    alternative = None
    is_released = False
    current_version = Version(API_VERSION)

    for entry in changelog:
        # Check for deprecation/removal entries
        if FMSG_CHANGELOG_DEPRECATED_IN_VERSION.split("{")[0] in entry:
            is_deprecated = True
            # Extract alternative from deprecation message if possible
            with suppress(IndexError, AttributeError):
                alternative = entry.split("Please use `")[1].split("`")[0]

        # Check for new version entries to determine if this is unreleased
        elif FMSG_CHANGELOG_NEW_IN_VERSION.split("{")[0] in entry:
            try:
                version_str = entry.split("New in *version ")[1].split("*")[0]
                entry_version = Version(version_str)
                # If the first/earliest entry version is greater than current API version,
                # this endpoint is not yet released
                if current_version < entry_version:
                    is_released = True
            except (IndexError, ValueError, AttributeError):
                pass

    # Set route options based on endpoint state
    route_options["include_in_schema"] = is_released
    route_options["deprecated"] = is_deprecated

    # Create description
    route_options["description"] = create_route_description(
        base=base_description,
        changelog=changelog,
        deprecated_in=(
            "Unknown" if is_deprecated else None
        ),  # We don't extract exact version
        alternative=alternative,
    )

    return route_options
