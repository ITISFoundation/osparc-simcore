from fastapi import Request
from servicelib.fastapi.dependencies import get_app, get_reverse_url_mapper

from ...services.director_v2 import DirectorV2Client

assert get_app  # nosec
assert get_reverse_url_mapper  # nosec


def get_director_v2_client(request: Request) -> DirectorV2Client:
    return DirectorV2Client.get_from_app_state(get_app(request))


__all__: tuple[str, ...] = (
    "get_app",
    "get_reverse_url_mapper",
)
