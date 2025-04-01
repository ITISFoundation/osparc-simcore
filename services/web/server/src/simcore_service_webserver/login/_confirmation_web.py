from urllib.parse import quote

from aiohttp import web
from yarl import URL


def _url_for_confirmation(app: web.Application, code: str) -> URL:
    # NOTE: this is in a query parameter, and can contain ? for example.
    safe_code = quote(code, safe="")
    return app.router["auth_confirmation"].url_for(code=safe_code)


def make_confirmation_link(request: web.Request, code: str) -> str:
    assert code  # nosec
    link = _url_for_confirmation(request.app, code=code)
    return f"{request.scheme}://{request.host}{link}"
