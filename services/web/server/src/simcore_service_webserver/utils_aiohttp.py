import io
import logging
from typing import Any, Callable, Generic, Literal, Optional, TypeVar

from aiohttp import web
from aiohttp.web_exceptions import HTTPError, HTTPException
from aiohttp.web_routedef import RouteDef, RouteTableDef
from models_library.generics import Envelope
from pydantic import Field
from pydantic.generics import GenericModel
from servicelib.common_headers import X_FORWARDED_PROTO
from servicelib.json_serialization import json_dumps
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from yarl import URL

from ._constants import INDEX_RESOURCE_NAME

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
                    request.headers.get(X_FORWARDED_PROTO, request.url.scheme)
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
    # NOTE: see https://github.com/ITISFoundation/osparc-simcore/issues/3646
    if issubclass(status_cls, HTTPError):
        enveloped = Envelope[Any](error=obj)
    else:
        enveloped = Envelope[Any](data=obj)

    return web.Response(
        text=json_dumps(enveloped.dict(**RESPONSE_MODEL_POLICY)),
        content_type=MIMETYPE_APPLICATION_JSON,
        status=status_cls.status_code,
    )


#
# Special models and responses for the front-end
#


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
    log.debug("page: '%s' parameters: '%s'", page, parameters)
    assert page in ("view", "error")  # nosec

    # NOTE: uniform encoding in front-end using url fragments
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1975
    fragment_path = f"{URL.build(path=f'/{page}').with_query(parameters)}"
    redirect_url = (
        app.router[INDEX_RESOURCE_NAME].url_for().with_fragment(fragment_path)
    )
    return web.HTTPFound(location=redirect_url)


PageParameters = TypeVar("PageParameters")


class NextPage(GenericModel, Generic[PageParameters]):
    """
    This is the body of a 2XX response to pass the front-end
    what kind of page shall be display next and some information about it

    An analogous structure is used in the redirects (see create_redirect_response) but
    using a path+query in the fragment of the URL
    """

    name: str = Field(..., description="Code name to the front-end page")
    parameters: Optional[PageParameters] = None

    def as_redirect_response(self, app: web.Application) -> web.HTTPFound:
        return create_redirect_response(
            app=app, page=self.name, **self.parameters.dict()
        )
