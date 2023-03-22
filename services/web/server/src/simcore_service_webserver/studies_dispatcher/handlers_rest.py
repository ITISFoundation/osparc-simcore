""" Handles requests to the Rest API

NOTE: openapi section for these handlers was generated using
   services/web/server/tests/sandbox/viewers_openapi_generator.py
"""
from typing import Optional

from aiohttp import web
from aiohttp.web import Request
from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl

from .._meta import API_VTAG
from ._core import ViewerInfo, list_viewers_info
from .handlers_redirects import compose_dispatcher_prefix_url

#
# API Models
#


class Viewer(BaseModel):
    """
    API model for a viewer resource

    A viewer is a service with an associated filetype.
    You can think of it as a tuple (filetype, service)

    The service could consume other filetypes BUT at this
    interface this is represented in yet another viewer resource

    For instance, the same service can be in two different viewer resources
      - viewer1=(JPEG, RawGraph service)
      - viewer2=(CSV, RawGraph service)

    A viewer can be dispatched using the view_url and appending the
    """

    title: str = Field(
        ..., description="Short formatted label with name and version of the viewer"
    )
    file_type: str = Field(..., description="Identifier for the file type")
    view_url: HttpUrl = Field(
        ...,
        description="Base url to execute viewer. Needs appending file_size,[file_name] and download_link as query parameters",
    )

    @classmethod
    def create(cls, request: Request, viewer: ViewerInfo):
        return cls(
            file_type=viewer.filetype,
            title=viewer.title,
            view_url=compose_dispatcher_prefix_url(
                request,
                viewer,
            ),
        )


#
# API Handlers
#

routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/services", name="list_services")
async def list_services(request: Request):
    """Returns a list latest version of services"""
    raise NotImplementedError("Still not implemented")


@routes.get(f"/{API_VTAG}/viewers", name="list_viewers")
async def list_viewers(request: Request):
    # filter: file_type=*
    file_type: Optional[str] = request.query.get("file_type", None)

    viewers = [
        Viewer.create(request, viewer).dict()
        for viewer in await list_viewers_info(request.app, file_type=file_type)
    ]
    return viewers


@routes.get(f"/{API_VTAG}/viewers/default", name="list_default_viewers")
async def list_default_viewers(request: Request):
    # filter: file_type=*
    file_type: Optional[str] = request.query.get("file_type", None)

    viewers = [
        Viewer.create(request, viewer).dict()
        for viewer in await list_viewers_info(
            request.app, file_type=file_type, only_default=True
        )
    ]
    return viewers


rest_handler_functions = {
    fun.__name__: fun for fun in [list_default_viewers, list_viewers]
}
