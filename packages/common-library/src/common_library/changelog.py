"""
CHANGELOG formatted-messages for API routes

- Append at the bottom of the route's description
- These are displayed in the swagger/redoc doc
- These are displayed in client's doc as well (auto-generator)
- Inspired on this idea https://www.sphinx-doc.org/en/master/usage/restructuredtext/directives.html#describing-changes-between-versions
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import Enum, auto
from typing import Any, ClassVar, cast

from packaging.version import Version


class ChangelogType(Enum):
    """Types of changelog entries in their lifecycle order"""

    NEW = auto()
    CHANGED = auto()
    DEPRECATED = auto()
    RETIRED = auto()


class ChangelogEntryAbstract(ABC):
    """Base class for changelog entries"""

    entry_type: ClassVar[ChangelogType]

    @abstractmethod
    def to_string(self) -> str:
        """Converts entry to a formatted string for documentation"""

    @abstractmethod
    def get_version(self) -> Version | None:
        """Returns the version associated with this entry, if any"""


class NewEndpoint(ChangelogEntryAbstract):
    """Indicates when an endpoint was first added"""

    entry_type = ChangelogType.NEW

    def __init__(self, version: str):
        self.version = version

    def to_string(self) -> str:
        return f"New in *version {self.version}*\n"

    def get_version(self) -> Version:
        return Version(self.version)


class ChangedEndpoint(ChangelogEntryAbstract):
    """Indicates a change to an existing endpoint"""

    entry_type = ChangelogType.CHANGED

    def __init__(self, version: str, message: str):
        self.version = version
        self.message = message

    def to_string(self) -> str:
        return f"Changed in *version {self.version}*: {self.message}\n"

    def get_version(self) -> Version:
        return Version(self.version)


class DeprecatedEndpoint(ChangelogEntryAbstract):
    """Indicates an endpoint is deprecated and should no longer be used"""

    entry_type = ChangelogType.DEPRECATED

    def __init__(self, alternative_route: str, version: str | None = None):
        self.alternative_route = alternative_route
        self.version = version

    def to_string(self) -> str:
        base_message = "🚨 **Deprecated**"
        if self.version:
            base_message += f" in *version {self.version}*"

        return (
            f"{base_message}: This endpoint is deprecated and will be removed in a future release.\n"
            f"Please use `{self.alternative_route}` instead.\n\n"
        )

    def get_version(self) -> Version | None:
        return Version(self.version) if self.version else None


class RetiredEndpoint(ChangelogEntryAbstract):
    """Indicates when an endpoint will be or was removed"""

    entry_type = ChangelogType.RETIRED

    def __init__(self, version: str, message: str):
        self.version = version
        self.message = message

    def to_string(self) -> str:
        return f"Retired in *version {self.version}*: {self.message}\n"

    def get_version(self) -> Version:
        return Version(self.version)


def create_route_description(
    *,
    base: str = "",
    changelog: Sequence[ChangelogEntryAbstract] | None = None,
) -> str:
    """
    Builds a consistent route description with optional changelog information.

    Args:
        base (str): Main route description.
        changelog (Sequence[ChangelogEntry]): List of changelog entries.

    Returns:
        str: Final description string.
    """
    parts = []

    if base:
        parts.append(base)

    if changelog:
        changelog_strings = [entry.to_string() for entry in changelog]
        parts.append("\n".join(changelog_strings))

    return "\n\n".join(parts)


def validate_changelog(changelog: Sequence[ChangelogEntryAbstract]) -> None:
    """
    Validates that the changelog entries follow the correct lifecycle order.

    Args:
        changelog: List of changelog entries to validate

    Raises:
        ValueError: If the changelog entries are not in a valid order
    """
    if not changelog:
        return

    # Check each entry's type is greater than or equal to the previous
    prev_type = None
    for entry in changelog:
        if prev_type is not None and entry.entry_type.value < prev_type.value:
            msg = (
                f"Changelog entries must be in lifecycle order. "
                f"Found {entry.entry_type.name} after {prev_type.name}."
            )
            raise ValueError(msg)
        prev_type = entry.entry_type

    # Ensure there's exactly one NEW entry as the first entry
    if changelog and changelog[0].entry_type != ChangelogType.NEW:
        msg = "First changelog entry must be NEW type"
        raise ValueError(msg)

    # Ensure there's at most one DEPRECATED entry
    deprecated_entries = [
        e for e in changelog if e.entry_type == ChangelogType.DEPRECATED
    ]
    if len(deprecated_entries) > 1:
        msg = "Only one DEPRECATED entry is allowed in a changelog"
        raise ValueError(msg)

    # Ensure all versions are valid
    for entry in changelog:
        version = entry.get_version()
        if version is None and entry.entry_type != ChangelogType.DEPRECATED:
            msg = f"Entry of type {entry.entry_type.name} must have a valid version"
            raise ValueError(msg)


def create_route_config(
    base_description: str = "",
    *,
    current_version: str | Version,
    changelog: Sequence[ChangelogEntryAbstract] | None = None,
) -> dict[str, Any]:
    """
    Creates route configuration options including description based on changelog entries.

    The function analyzes the changelog to determine if the endpoint:
    - Is released and visible (if the earliest entry version is not in the future and not removed)
    - Is deprecated (if there's a DEPRECATED entry in the changelog)

    Args:
        base_description: Main route description
        current_version: Current version of the API
        changelog: List of changelog entries indicating version history

    Returns:
        dict: Route configuration options that can be used as kwargs for route decorators
    """
    route_options: dict[str, Any] = {}
    changelog_list = list(changelog) if changelog else []

    validate_changelog(changelog_list)

    if isinstance(current_version, str):
        current_version = Version(current_version)

    # Determine endpoint state
    is_deprecated = False
    is_released = True  # Assume released by default
    is_removed = False

    # Get the first entry (NEW) to check if released
    if changelog_list and changelog_list[0].entry_type == ChangelogType.NEW:
        first_entry = cast(NewEndpoint, changelog_list[0])
        first_version = first_entry.get_version()
        if first_version and first_version > current_version:
            is_released = False

    # Check for deprecation and removal
    for entry in changelog_list:
        if entry.entry_type == ChangelogType.DEPRECATED:
            is_deprecated = True
        elif entry.entry_type == ChangelogType.RETIRED:
            is_removed = True

    # Set route options based on endpoint state
    # An endpoint is included in schema if it's released and not removed
    route_options["include_in_schema"] = is_released and not is_removed
    route_options["deprecated"] = is_deprecated

    # Create description
    route_options["description"] = create_route_description(
        base=base_description,
        changelog=changelog_list,
    )

    return route_options
