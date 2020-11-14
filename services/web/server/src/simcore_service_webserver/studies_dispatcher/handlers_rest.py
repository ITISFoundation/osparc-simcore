""" Handles requests to the Rest API

"""
from aiohttp import web
from pydantic import BaseModel

from ._core import (
    find_compatible_viewer,
    ViewerInfo,
    ValidationMixin,
    MatchNotFoundError,
)


class RequestParams(BaseModel, ValidationMixin):
    # TODO: create dinamically with pydantic class
    file_name: str
    file_size: int  # mime-types
    file_type: str  # Bytes


async def get_viewers_handler(request: web.Request):
    try:
        p = RequestParams.create_from(request)

        # find the best viewer match for file setup (tmp hard-coded)
        viewer: ViewerInfo = find_compatible_viewer(p.file_size, p.file_type)

        return {
            "name": viewer.label,
            # "description": "some meaninful descpriton",
            "base_url": request.app.router["get_redirection_to_viewer"]
            .url_for()
            .with_query(**p.dict()),
            # TODO: make sure parameters are always in syn
        }

    except MatchNotFoundError as err:
        raise web.HTTPUnprocessableEntity(reason=err.reason)
