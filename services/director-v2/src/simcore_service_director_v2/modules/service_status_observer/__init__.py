from fastapi import FastAPI

from . import _store
from ._store import remove_from_status_cache


def setup(app: FastAPI) -> None:
    _store.setup_statuses_store(app)


__all__: tuple[str, ...] = (
    "remove_from_status_cache",
    "setup",
)
