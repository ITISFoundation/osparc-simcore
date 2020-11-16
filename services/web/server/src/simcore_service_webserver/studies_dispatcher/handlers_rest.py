""" Handles requests to the Rest API

"""
from aiohttp import web
from pydantic import BaseModel
from typing import Optional

from ._core import (
    MatchNotFoundError,
    ValidationMixin,
    ViewerInfo,
    find_compatible_viewer,
    iter_supported_filetypes,
)


# GET /v0/viewers/filetypes
async def list_supported_filetypes(request: web.Request):
    data = []
    for file_type, viewer in iter_supported_filetypes():
        data.append(
            {
                "file_type": file_type,
                "viewer_title": viewer.title,
                "redirection_url": request.app.router["get_redirection_to_viewer"]
                .url_for()
                .with_query(file_type=file_type),
            }
        )
    return data


# GET /v0/viewers -----
class RequestParams(BaseModel, ValidationMixin):
    # TODO: create dinamically with pydantic class
    file_name: Optional[str] = None
    file_size: Optional[int] = None  # TODO: mime-types
    file_type: str  # Bytes


async def get_viewer_for_file(request: web.Request):
    try:
        p = RequestParams.create_from(request)

        # find the best viewer match for file setup (tmp hard-coded)
        viewer: ViewerInfo = find_compatible_viewer(p.file_size, p.file_type)

        return {
            "file_type": p.file_type,
            "viewer_title": viewer.title,
            "redirection_url": request.app.router["get_redirection_to_viewer"]
            .url_for()
            .with_query(
                **p.dict(exclude_defaults=True, exclude_unset=True, exclude_none=True)
            ),
        }

    except MatchNotFoundError as err:
        raise web.HTTPUnprocessableEntity(reason=err.reason)
