import io
import logging
from collections.abc import Callable, Iterator
from typing import Any, Generic, Literal, TypeAlias, TypeVar

from aiohttp import web
from aiohttp.web_exceptions import HTTPError, HTTPException
from aiohttp.web_routedef import RouteDef, RouteTableDef
from common_library.json_serialization import json_dumps
from common_library.network import is_ip_address
from models_library.generics import Envelope
from models_library.rest_pagination import ItemT, Page
from pydantic import BaseModel, Field
from servicelib.common_headers import X_FORWARDED_PROTO
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from yarl import URL

from .constants import INDEX_RESOURCE_NAME

_logger = logging.getLogger(__name__)


def rename_routes_as_handler_function(routes: RouteTableDef, *, prefix: str):
    for route in routes:
        assert isinstance(route, RouteDef)  # nosec
        route.kwargs["name"] = f"{prefix}.{route.handler.__name__}"


def get_routes_view(routes: RouteTableDef) -> str:
    fh = io.StringIO()
    print(routes, file=fh)
    for r in routes:
        print(" ", r, file=fh)
    return fh.getvalue()


def create_url_for_function(
    app: web.Application, url: URL, headers: dict[str, str]
) -> Callable:

    def _url_for(route_name: str, **params: dict[str, Any]) -> str:
        """Reverse URL constructing using named resources"""
        try:
            rel_url: URL = app.router[route_name].url_for(
                **{k: f"{v}" for k, v in params.items()}
            )
            _url: URL = (
                url.origin()
                .with_scheme(
                    # Custom header by traefik. See labels in docker-compose as:
                    # - traefik.http.middlewares.${SWARM_STACK_NAME_NO_HYPHEN}_sslheader.headers.customrequestheaders.X-Forwarded-Proto=http
                    headers.get(X_FORWARDED_PROTO, url.scheme)
                )
                .with_path(str(rel_url))
            )
            return f"{_url}"

        except KeyError as err:
            msg = f"Cannot find URL because there is no resource registered as {route_name=}Check name spelling or whether the router was not registered"
            raise RuntimeError(msg) from err

    return _url_for


def envelope_json_response(
    obj: Any, status_cls: type[HTTPException] = web.HTTPOk
) -> web.Response:
    # NOTE: see https://github.com/ITISFoundation/osparc-simcore/issues/3646
    if issubclass(status_cls, HTTPError):
        enveloped = Envelope[Any](error=obj)
    else:
        enveloped = Envelope[Any](data=obj)

    return web.Response(
        text=json_dumps(enveloped.model_dump(**RESPONSE_MODEL_POLICY)),
        content_type=MIMETYPE_APPLICATION_JSON,
        status=status_cls.status_code,
    )


def create_json_response_from_page(page: Page[ItemT]) -> web.Response:
    return web.Response(
        text=page.model_dump_json(**RESPONSE_MODEL_POLICY),
        content_type=MIMETYPE_APPLICATION_JSON,
    )


#
# Special models and responses for the front-end
#

PageStr: TypeAlias = Literal["view", "error"]


def create_redirect_to_page_response(
    app: web.Application, page: PageStr, **parameters
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
    _logger.debug("page: '%s' parameters: '%s'", page, parameters)
    assert page in ("view", "error")  # nosec

    # NOTE: uniform encoding in front-end using url fragments
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1975
    fragment_path = f"{URL.build(path=f'/{page}').with_query(parameters)}"
    redirect_url = (
        app.router[INDEX_RESOURCE_NAME].url_for().with_fragment(fragment_path)
    )
    return web.HTTPFound(location=redirect_url)


PageParameters = TypeVar("PageParameters", bound=BaseModel)


class NextPage(BaseModel, Generic[PageParameters]):
    """
    This is the body of a 2XX response to pass the front-end
    what kind of page shall be display next and some information about it

    An analogous structure is used in the redirects (see create_redirect_response) but
    using a path+query in the fragment of the URL
    """

    name: str = Field(
        ..., description="Code name to the front-end page. Ideally a PageStr"
    )
    parameters: PageParameters | None = None


def iter_origins(request: web.Request) -> Iterator[tuple[str, str]]:
    #
    # SEE https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-Host
    # SEE https://doc.traefik.io/traefik/getting-started/faq/#what-are-the-forwarded-headers-when-proxying-http-requests
    seen = set()

    # X-Forwarded-Proto and X-Forwarded-Host can contain a comma-separated list of protocols and hosts
    # (when the request passes through multiple proxies)
    fwd_protos = [
        p.strip()
        for p in request.headers.get("X-Forwarded-Proto", "").split(",")
        if p.strip()
    ]
    fwd_hosts = [
        h.strip()
        for h in request.headers.get("X-Forwarded-Host", "").split(",")
        if h.strip()
    ]

    if fwd_protos and fwd_hosts:
        for proto, host in zip(fwd_protos, fwd_hosts, strict=False):
            if (proto, host) not in seen:
                seen.add((proto, host))
                yield (proto, host.partition(":")[0])  # strip port

    # fallback to request scheme/host
    yield request.scheme, f"{request.host.partition(':')[0]}"


def get_api_base_url(request: web.Request) -> str:
    scheme, host = next(iter_origins(request))
    api_host = api_host = host if is_ip_address(host) else f"api.{host}"
    return f"{scheme}://{api_host}"
