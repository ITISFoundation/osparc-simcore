import io
import logging
from typing import Any, Callable, Literal

from aiohttp import web
from aiohttp.web_exceptions import HTTPError, HTTPException
from aiohttp.web_routedef import RouteDef, RouteTableDef
from models_library.generics import Envelope
from servicelib.json_serialization import json_dumps
from yarl import URL

from ._constants import INDEX_RESOURCE_NAME
from .rest_constants import RESPONSE_MODEL_POLICY

log = logging.getLogger(__name__)


def rename_routes_as_handler_function(routes: RouteTableDef, *, prefix: str):
    route: RouteDef
    for route in routes:  # type: ignore
        route.kwargs["name"] = f"{prefix}.{route.handler.__name__}"


def get_routes_view(routes: RouteTableDef) -> str:
    fh = io.StringIO()
    print(routes, file=fh)
    for r in routes:
        print(" ", r, file=fh)
    return fh.getvalue()


def create_url_for_function(request: web.Request) -> Callable:
    app = request.app

    def url_for(route_name: str, **params: dict[str, Any]) -> str:
        """Reverse URL constructing using named resources"""
        try:
            rel_url: URL = app.router[route_name].url_for(
                **{k: f"{v}" for k, v in params.items()}
            )
            url = (
                request.url.origin()
                .with_scheme(
                    # Custom header by traefik. See labels in docker-compose as:
                    # - traefik.http.middlewares.${SWARM_STACK_NAME_NO_HYPHEN}_sslheader.headers.customrequestheaders.X-Forwarded-Proto=http
                    request.headers.get("X-Forwarded-Proto", request.url.scheme)
                )
                .with_path(str(rel_url))
            )
            return f"{url}"

        except KeyError as err:
            raise RuntimeError(
                f"Cannot find URL because there is no resource registered as {route_name=}"
                "Check name spelling or whether the router was not registered"
            ) from err

    return url_for


def envelope_json_response(
    obj: Any, status_cls: type[HTTPException] = web.HTTPOk
) -> web.Response:
    # TODO: replace all envelope functionality form packages/service-library/src/servicelib/aiohttp/rest_responses.py
    # TODO: Remove middleware to envelope handler responses at packages/service-library/src/servicelib/aiohttp/rest_middlewares.py: envelope_middleware_factory and use instead this
    # TODO: review error_middleware_factory
    if issubclass(status_cls, HTTPError):
        enveloped = Envelope[Any](error=obj)
    else:
        enveloped = Envelope[Any](data=obj)

    return web.Response(
        text=json_dumps(enveloped.dict(**RESPONSE_MODEL_POLICY)),
        content_type="application/json",
        status=status_cls.status_code,
    )


def create_redirect_response(
    app: web.Application, page: Literal["view", "error"], **parameters
) -> web.HTTPFound:
    """
    Returns a redirect response to the front-end with information on page
    and parameters embedded in the fragment.

    For instance,
        https://osparc.io/#/error?message=Sorry%2C%20I%20could%20not%20find%20this%20&status_code=404
    results from
            - page=error
        and parameters
            - message="Sorry, I could not find this"
            - status_code=404

    Front-end can then render this data either in an error or a view page
    """
    # TODO: Uniform encoding in front-end fragments  https://github.com/ITISFoundation/osparc-simcore/issues/1975
    log.debug("page: '%s' parameters: '%s'", page, parameters)

    page = page.strip(" /")
    assert page in ("view", "error")  # nosec
    fragment_path = str(URL.build(path=f"/{page}").with_query(parameters))
    redirect_url = (
        app.router[INDEX_RESOURCE_NAME].url_for().with_fragment(fragment_path)
    )
    return web.HTTPFound(location=redirect_url)
