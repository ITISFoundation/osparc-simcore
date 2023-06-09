from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

#
# DEPENDENCIES
#


assert get_reverse_url_mapper  # nosec
assert get_app  # nosec

__all__: tuple[str, ...] = (
    "get_reverse_url_mapper",
    "get_app",
)
