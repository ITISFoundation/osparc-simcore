from aiohttp.web import HTTPBadRequest


class SDSException(HTTPBadRequest):  # pylint: disable=too-many-ancestors
    # NOTE: all these errors will displayed to the user
    """Basic exception for errors raised inside the module"""

    def __init__(self, message: str):
        # Multiline not allowed in HTTP reason attribute
        super().__init__(reason=message.replace("\n", " ") if message else None)
