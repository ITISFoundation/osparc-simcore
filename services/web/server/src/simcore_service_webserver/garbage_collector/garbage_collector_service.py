"""Garbage collector public facade per DESIGN.md §133-152."""

# Constants
# Functions
from ._core import collect_garbage
from .settings import GUEST_USER_RC_LOCK_FORMAT

__all__: tuple[str, ...] = (
    # Constants
    "GUEST_USER_RC_LOCK_FORMAT",
    # Functions
    "collect_garbage",
)  # nopycln: file
