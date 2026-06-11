"""Announcements public facade per DESIGN.md §133-152."""

# Functions
from ._api import list_announcements

__all__: tuple[str, ...] = (
    # functions
    "list_announcements",
)  # nopycln: file
