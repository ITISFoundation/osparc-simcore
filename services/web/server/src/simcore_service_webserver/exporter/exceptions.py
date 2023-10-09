from aiohttp.web import HTTPBadRequest


class SDSException(HTTPBadRequest):  # pylint: disable=too-many-ancestors
    # NOTE: all these errors will displayed to the user
    """Basic exception for errors raised inside the module"""

    def __init__(self, message: str):
        super().__init__(reason=message)
