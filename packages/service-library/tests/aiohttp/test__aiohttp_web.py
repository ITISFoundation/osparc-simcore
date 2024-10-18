from aiohttp import web
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON


def test_http_errors():

    err = web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
