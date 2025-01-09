# mypy: disable-error-code=truthy-function
from fastapi import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

from ...core.settings import ApplicationSettings


def get_settings(request: Request) -> ApplicationSettings:
    settings = request.app.state.settings
    assert isinstance(settings, ApplicationSettings)  # nosec
    return settings


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
