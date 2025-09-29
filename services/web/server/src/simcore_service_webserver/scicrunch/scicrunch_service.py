from typing import Final

from aiohttp import web

from ._service import ScicrunchResourcesService

SCICRUNCH_SERVICE_APPKEY: Final = web.AppKey(
    ScicrunchResourcesService.__name__, ScicrunchResourcesService
)


__all__: tuple[str, ...] = ("SCICRUNCH_SERVICE_APPKEY",)
# nopycln: file
