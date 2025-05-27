from aiohttp.web import HTTPBadRequest
from servicelib.aiohttp.rest_responses import safe_status_message


class SDSException(HTTPBadRequest):  # pylint: disable=too-many-ancestors
    # NOTE: all these errors will displayed to the user
    """Basic exception for errors raised inside the module"""

    def __init__(self, message: str):
        super().__init__(reason=safe_status_message(message))
