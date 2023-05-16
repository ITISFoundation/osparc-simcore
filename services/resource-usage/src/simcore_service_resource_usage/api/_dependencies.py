import logging
from typing import Any, Callable

from fastapi import Request
from starlette.datastructures import URL

from ..core.settings import ApplicationSettings

logger = logging.getLogger(__name__)


#
# DEPENDENCIES
#


def get_reverse_url_mapper(request: Request) -> Callable:
    def _reverse_url_mapper(name: str, **path_params: Any) -> str:
        url: URL = request.url_for(name, **path_params)
        return f"{url}"

    return _reverse_url_mapper


def get_settings(request: Request) -> ApplicationSettings:
    app_settings: ApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings
