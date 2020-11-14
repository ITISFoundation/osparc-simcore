""" Handles requests to the Rest API

"""
from aiohttp import web


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
