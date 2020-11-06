import uuid

from aiohttp import web


rest_routes = web.RouteTableDef()


@rest_routes.get("/viewers")
async def get_viewers_handler(request: web.Request):
    file_name: str = request.query["file_name"]
    file_type: str = request.query["file_type"]  # mime-types
    file_size: int = request.query["file_size"]  # Bytes

    # find the best viewer match for file setup (tmp hard-coded)

    #
    # consider size limitations and type to determine file
    #

    # check if viewer is available in catalog

    # key =  encode file_name, type, size and service_key in a single string
    #       so it can be decoded on the other side
    encoded_key = f"{file_name}&&{file_type}&&{file_size}"

    # respond with a list of viewers and po
    return {
        "name": "viewer-human-readable-name",
        "description": "some meaninful descpriton",
        "base_url": request.app.router["get_redirection_to_viewer"].url_for(
            key=encoded_key
        ),
    }


page_routes = web.RouteTableDef()

from pydantic import BaseModel, HttpUrl, ValidationError
from typing import Optional


# TODO: create dinamically pydantic class
class RequestParams(BaseModel):
    file_name: Optional[str] = None
    file_size: int
    file_type: str
    download_link: HttpUrl


@page_routes.get("/view", name="get_redirection_to_viewer")
async def get_redirection_to_viewer_with_specs(request: web.Request):
    try:
        params = RequestParams(**request.query.keys())
    except ValidationError as err:
        raise web.HTTPBadRequest(content_type="application/json", data=err.json())

    return await get_redirection_to_viewer_impl(request.app, **params)



@page_routes.get("/view/{key}", name="get_redirection_to_viewer")
async def get_redirection_to_viewer(request: web.Request):
    file_name, file_size = request.query["key"]
    download_link = request.query["src"]




def get_redirection_to_viewer_impl(app: web.Application, *, file_name: str, file_size: int, download_link: HttpUrl):

    # how to gurantee that the metadata is the same??

    # create guest user (if not authorized)

    # create project with file-picker (download_link) and viewer

    # spawn task to open project

    # get node-uuid from viewer
    viewer_uuid = uuid.uuid4()

    # info for the front-end
    info = {
        "iframe_path": f"/x/{viewer_uuid}",
        "file_name": file_name, # to display while waiting
        "file_size": file_size, # to display estimated load time
    }


    viewer_page_url = (
        app.router["main"].url_for().with_fragment()
    )
    raise web.HTTPFound(location=viewer_page_url)




def setup_guest_pages(app: web.Application):
    raise NotImplementedError()
