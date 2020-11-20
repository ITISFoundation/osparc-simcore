""" Handles requests to the Rest API

"""
from typing import Optional

from aiohttp import web
from pydantic import BaseModel, Field
from pydantic.types import PositiveInt

from ._core import (
    MatchNotFoundError,
    ValidationMixin,
    ViewerInfo,
    find_compatible_viewer,
    iter_supported_filetypes,
)


def _get_redirect_url(request: web.Request, **query_params) -> str:
    absolute_url = request.url.join(
        request.app.router["get_redirection_to_viewer"]
        .url_for()
        .with_query(**query_params)
    )
    return str(absolute_url)


# GET /v0/viewers/filetypes
async def list_supported_filetypes(request: web.Request):
    data = []
    for file_type, viewer in iter_supported_filetypes():
        data.append(
            {
                "file_type": file_type,
                "viewer_title": viewer.title,
                "redirection_url": _get_redirect_url(request, file_type=file_type),
            }
        )
    return data


# GET /v0/viewers -----
# TODO: create dynamically with pydantic class: https://pydantic-docs.helpmanual.io/usage/models/#dynamic-model-creation
class RequestParams(BaseModel, ValidationMixin):
    file_type: str  # TODO: mime-types??
    file_name: Optional[str] = None
    file_size: Optional[PositiveInt] = Field(
        None, description="Expected file size in bytes"
    )


async def get_viewer_for_file(request: web.Request):
    try:
        params = RequestParams.from_request(request)

        # find the best viewer match for file setup (tmp hard-coded)
        viewer: ViewerInfo = find_compatible_viewer(params.file_type, params.file_size)

        return {
            "file_type": params.file_type,
            "viewer_title": viewer.title,
            "redirection_url": _get_redirect_url(
                request,
                **params.dict(
                    exclude_defaults=True, exclude_unset=True, exclude_none=True
                )
            ),
        }

    except MatchNotFoundError as err:
        raise web.HTTPUnprocessableEntity(reason=err.reason)


rest_handler_functions = {
    fun.__name__: fun for fun in [list_supported_filetypes, get_viewer_for_file]
}
