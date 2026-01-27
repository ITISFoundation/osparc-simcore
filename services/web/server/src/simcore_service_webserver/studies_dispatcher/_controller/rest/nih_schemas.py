import logging
from dataclasses import asdict

from aiohttp import web
from aiohttp.web import Request
from models_library.services import ServiceKey
from models_library.services_types import ServiceVersion
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
)
from pydantic.networks import HttpUrl

from ..._catalog import ServiceMetaData
from ..._models import ViewerInfo
from .redirects_schemas import ViewerQueryParams

_logger = logging.getLogger(__name__)


#
# HELPERS to compose redirects
#


def _compose_file_and_service_dispatcher_prefix_url(request: web.Request, viewer: ViewerInfo) -> HttpUrl:
    """This is denoted PREFIX URL because it needs to append extra query parameters"""
    params = ViewerQueryParams.from_viewer(viewer).model_dump()
    absolute_url = request.url.join(request.app.router["get_redirection_to_viewer"].url_for().with_query(**params))
    absolute_url_: HttpUrl = TypeAdapter(HttpUrl).validate_python(f"{absolute_url}")
    return absolute_url_


def _compose_service_only_dispatcher_prefix_url(
    request: web.Request, service_key: str, service_version: str
) -> HttpUrl:
    params = ViewerQueryParams(
        viewer_key=TypeAdapter(ServiceKey).validate_python(service_key),
        viewer_version=TypeAdapter(ServiceVersion).validate_python(service_version),
    ).model_dump(exclude_none=True, exclude_unset=True)
    absolute_url = request.url.join(request.app.router["get_redirection_to_viewer"].url_for().with_query(**params))
    absolute_url_: HttpUrl = TypeAdapter(HttpUrl).validate_python(f"{absolute_url}")
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

    title: str = Field(..., description="Short formatted label with name and version of the viewer")
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

    @field_validator("file_extensions")
    @classmethod
    def remove_dot_prefix_from_extension(cls, v):
        if v:
            return [ext.removeprefix(".") for ext in v]
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "simcore/services/dynamic/sim4life",
                "title": "Sim4Life Mattermost",
                "description": "It is also sim4life for the web",
                "thumbnail": "https://via.placeholder.com/170x120.png",
                "file_extensions": ["smash", "h5"],
                "view_url": "https://host.com/view?viewer_key=simcore/services/dynamic/raw-graphs&viewer_version=1.2.3",
            }
        }
    )
