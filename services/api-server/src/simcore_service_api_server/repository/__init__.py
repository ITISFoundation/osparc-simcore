# mypy: disable-error-code=truthy-function
from ._base import BaseRepository

assert BaseRepository  # nosec
__all__: tuple[str, ...] = ("BaseRepository",)
