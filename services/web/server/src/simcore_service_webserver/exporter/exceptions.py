from aiohttp.web import HTTPBadRequest


class ExporterException(HTTPBadRequest):  # pylint: disable=too-many-ancestors
    """Basic exception for errors raised inside the exporter module"""

    def __init__(self, message: str):
        super().__init__(reason=message)
