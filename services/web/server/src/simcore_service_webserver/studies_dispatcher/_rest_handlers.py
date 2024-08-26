""" Handles requests to the Rest API

"""
import logging
from dataclasses import asdict
from typing import Any, ClassVar

from aiohttp import web
from aiohttp.web import Request
from models_library.services import ServiceKey
from models_library.services_types import ServiceVersion
from pydantic import BaseModel, Field, ValidationError, parse_obj_as, validator
from pydantic.networks import HttpUrl

from .._meta import API_VTAG
from ..products.api import get_product_name
from ..utils_aiohttp import envelope_json_response
from ._catalog import ServiceMetaData, iter_latest_product_services
from ._core import list_viewers_info
from ._models import ViewerInfo
from ._redirects_handlers import ViewerQueryParams

_logger = logging.getLogger(__name__)


#
# HELPERS to compose redirects
#


def _compose_file_and_service_dispatcher_prefix_url(
    request: web.Request, viewer: ViewerInfo
) -> HttpUrl:
    """This is denoted PREFIX URL because it needs to append extra query parameters"""
    params = ViewerQueryParams.from_viewer(viewer).dict()
    absolute_url = request.url.join(
        request.app.router["get_redirection_to_viewer"].url_for().with_query(**params)
    )
    absolute_url_: HttpUrl = parse_obj_as(HttpUrl, f"{absolute_url}")
    return absolute_url_


def _compose_service_only_dispatcher_prefix_url(
    request: web.Request, service_key: str, service_version: str
) -> HttpUrl:
    params = ViewerQueryParams(
        viewer_key=ServiceKey(service_key),
        viewer_version=ServiceVersion(service_version),
    ).dict(exclude_none=True, exclude_unset=True)
    absolute_url = request.url.join(
        request.app.router["get_redirection_to_viewer"].url_for().with_query(**params)
    )
    absolute_url_: HttpUrl = parse_obj_as(HttpUrl, f"{absolute_url}")
    return absolute_url_


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
            view_url=_compose_file_and_service_dispatcher_prefix_url(
                request,
                viewer,
            ),
        )


class ServiceGet(BaseModel):
    key: ServiceKey = Field(..., description="Service key ID")

    title: str = Field(..., description="Service name for display")
    description: str = Field(..., description="Long description of the service")
    thumbnail: HttpUrl = Field(..., description="Url to service thumbnail")

    # extra properties
    file_extensions: list[str] = Field(
        default_factory=list,
        description="File extensions that this service can process",
    )

    # actions
    view_url: HttpUrl = Field(
        ...,
        description="Redirection to open a service in osparc (see /view)",
    )

    @classmethod
    def create(cls, meta: ServiceMetaData, request: web.Request):
        return cls(
            view_url=_compose_service_only_dispatcher_prefix_url(
                request, service_key=meta.key, service_version=meta.version
            ),
            **asdict(meta),
        )

    @validator("file_extensions")
    @classmethod
    def remove_dot_prefix_from_extension(cls, v):
        if v:
            return [ext.removeprefix(".") for ext in v]
        return v

    class Config:
        schema_extra: ClassVar[dict[str, Any]] = {
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "title": "Sim4Life Mattermost",
                "description": "It is also sim4life for the web",
                "thumbnail": "https://via.placeholder.com/170x120.png",
                "file_extensions": ["smash", "h5"],
                "view_url": "https://host.com/view?viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=1.2.3",
            }
        }


#
# API Handlers
#


routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/services", name="list_latest_services")
async def list_latest_services(request: Request):
    """Returns a list latest version of services"""
    product_name = get_product_name(request)

    services = []
    async for service_data in iter_latest_product_services(
        request.app, product_name=product_name
    ):
        try:
            service = ServiceGet.create(service_data, request)
            services.append(service)
        except ValidationError as err:
            _logger.debug("Invalid %s: %s", f"{service_data=}", err)

    return envelope_json_response(services)


@routes.get(f"/{API_VTAG}/viewers", name="list_viewers")
async def list_viewers(request: Request):
    # filter: file_type=*
    file_type: str | None = request.query.get("file_type", None)

    viewers = [
        Viewer.create(request, viewer).dict()
        for viewer in await list_viewers_info(request.app, file_type=file_type)
    ]
    return envelope_json_response(viewers)


@routes.get(f"/{API_VTAG}/viewers/default", name="list_default_viewers")
async def list_default_viewers(request: Request):
    # filter: file_type=*
    file_type: str | None = request.query.get("file_type", None)

    viewers = [
        Viewer.create(request, viewer).dict()
        for viewer in await list_viewers_info(
            request.app, file_type=file_type, only_default=True
        )
    ]
    return envelope_json_response(viewers)


rest_handler_functions = {
    fun.__name__: fun for fun in [list_default_viewers, list_viewers]
}
