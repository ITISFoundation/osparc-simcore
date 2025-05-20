from typing import Final

#
# CHANGELOG formatted-messages for API routes
#
# - Append at the bottom of the route's description
# - These are displayed in the swagger doc
# - These are displayed in client's doc as well (auto-generator)
# - Inspired on this idea https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#describing-changes-between-versions
#

# new routes
FMSG_CHANGELOG_NEW_IN_VERSION: Final[str] = "New in *version {}*\n"

# new inputs/outputs in routes
FMSG_CHANGELOG_ADDED_IN_VERSION: Final[str] = "Added in *version {}*: {}\n"

# changes on inputs/outputs in routes
FMSG_CHANGELOG_CHANGED_IN_VERSION: Final[str] = "Changed in *version {}*: {}\n"

# removed on inputs/outputs in routes
FMSG_CHANGELOG_REMOVED_IN_VERSION_FORMAT: Final[str] = "Removed in *version {}*: {}\n"

FMSG_DEPRECATED_ROUTE_NOTICE: Final[str] = (
    "🚨 **Deprecated**: This endpoint is deprecated and will be removed in a future release.\n"
    "Please use `{}` instead.\n\n"
)

DEFAULT_MAX_STRING_LENGTH: Final[int] = 500


def create_route_description(
    *,
    base: str = "",
    deprecated: bool = False,
    alternative: str | None = None,  # alternative
    changelog: list[str] | None = None
) -> str:
    """
    Builds a consistent route/query description with optional deprecation and changelog information.

    Args:
        base (str): Main route/query description.
        deprecated (tuple): alternative_route if deprecated.
        changelog (List[str]): List of formatted changelog strings.

    Returns:
        str: Final description string.
    """
    parts = []

    if deprecated:
        assert alternative, "If deprecated, alternative must be provided"  # nosec
        parts.append(FMSG_DEPRECATED_ROUTE_NOTICE.format(alternative))

    if base:
        parts.append(base)

    if changelog:
        parts.append("\n".join(changelog))

    return "\n\n".join(parts)
