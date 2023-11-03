from fastapi import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

from ...core.settings import ApplicationSettings


def get_settings(request: Request) -> ApplicationSettings:
    app_settings: ApplicationSettings = request.app.state.settings
    assert app_settings  # nosec
    return app_settings


assert get_app  # nosec
assert get_reverse_url_mapper  # nosec


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
