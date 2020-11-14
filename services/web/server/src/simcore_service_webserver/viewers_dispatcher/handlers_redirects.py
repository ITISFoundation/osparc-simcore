""" Handles request to the viewers redirection entrypoints

"""

import uuid
from typing import Optional

from aiohttp import web
from pydantic import BaseModel, HttpUrl, ValidationError


class ValidationMixin:
    @classmethod
    def create_from(cls, request: web.Request):
        try:
            obj = cls(**request.query.keys())
        except ValidationError as err:
            raise web.HTTPBadRequest(content_type="application/json", body=err.json())
        else:
            return obj


# TODO: create dinamically pydantic class
class RequestParams(BaseModel, ValidationMixin):
    file_name: Optional[str] = None
    file_size: int
    file_type: str
    download_link: HttpUrl



async def get_redirection_to_viewer_with_specs(request: web.Request):
    params = RequestParams.create_from(request)

    return await get_redirection_to_viewer_impl(request.app, **params.dict())



async def get_redirection_to_viewer(request: web.Request):
    file_name, file_size = request.query["key"]
    download_link = request.query["src"]

    raise NotImplementedError()


def get_redirection_to_viewer_impl(
    app: web.Application, *, file_name: str, file_size: int, download_link: HttpUrl
):

    # how to gurantee that the metadata is the same??

    # create guest user (if not authorized) -> studies_access

    # create project with file-picker (download_link) and viewer

    # spawn task to open project -> studies_access

    # get node-uuid from viewer
    viewer_uuid = uuid.uuid4()

    # info for the front-end
    body = {
        "iframe_path": f"/x/{viewer_uuid}",
        "file_name": file_name,  # to display while waiting
        "file_size": file_size,  # to display estimated load time
    }

    viewer_page_url = app.router["main"].url_for().with_fragment()
    raise web.HTTPFound(location=viewer_page_url)
