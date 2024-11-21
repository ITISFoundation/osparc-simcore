from enum import Enum
from typing import Final

from fastapi import FastAPI

from . import _index, _services, _sse_utils
from ._constants import UI_MOUNT_PREFIX

_TAGS: Final[list[str | Enum]] = ["FastUI"]


def setup_ui_api(app: FastAPI) -> None:
    _sse_utils.setup_sse(app)
    _services.setup_services(app)

    app.include_router(_services.router, prefix=UI_MOUNT_PREFIX, tags=_TAGS)

    # keep as last entry
    app.include_router(_index.get_index_router(UI_MOUNT_PREFIX), tags=_TAGS)
