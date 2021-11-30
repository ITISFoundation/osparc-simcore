import io
from typing import Any, Callable, Optional, Type

from aiohttp import web
from aiohttp.web_exceptions import HTTPException
from aiohttp.web_routedef import RouteDef, RouteTableDef
from servicelib.json_serialization import json_dumps
from yarl import URL


def rename_routes_as_handler_function(routes: RouteTableDef, *, prefix: str):
    route: RouteDef
    for route in routes:  # type: ignore
        route.kwargs["name"] = f"{prefix}.{route.handler.__name__}"


def view_routes(routes: RouteTableDef):
    fh = io.StringIO()
    print(routes, file=fh)
    for r in routes:
        print(" ", r, file=fh)
    return fh.getvalue()


def create_url_for_function(request: web.Request) -> Callable:
    app = request.app

    def url_for(router_name: str, **params) -> Optional[str]:
        try:
            rel_url: URL = app.router[router_name].url_for(
                **{k: f"{v}" for k, v in params.items()}
            )
            url = (
                request.url.origin()
                .with_scheme(
                    request.headers.get("X-Forwarded-Proto", request.url.scheme)
                )
                .with_path(str(rel_url))
            )
            return f"{url}"

        except KeyError:
            return None

    return url_for


def enveloped_json_response(
    data: Any, status_cls: Type[HTTPException] = web.HTTPOk, **extra
) -> web.Response:
    # TODO: implement Envelop with generics
    enveloped: str = json_dumps({"data": data, **extra})
    return web.Response(
        text=enveloped, content_type="application/json", status=status_cls.status_code
    )
