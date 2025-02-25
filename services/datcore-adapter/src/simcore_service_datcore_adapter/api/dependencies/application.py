# mypy: disable-error-code=truthy-function

from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
