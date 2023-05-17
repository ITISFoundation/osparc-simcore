import logging
from typing import Any, Callable

from fastapi import Request
from starlette.datastructures import URL

logger = logging.getLogger(__name__)


#
# DEPENDENCIES
#


def get_reverse_url_mapper(request: Request) -> Callable:
    def _reverse_url_mapper(name: str, **path_params: Any) -> str:
        url: URL = request.url_for(name, **path_params)
        return f"{url}"

    return _reverse_url_mapper
