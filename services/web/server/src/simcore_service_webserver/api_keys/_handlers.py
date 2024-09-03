import logging

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_webserver.auth import ApiKeyCreate
from models_library.users import UserID
from pydantic import Field
from servicelib.aiohttp.requests_validation import RequestParams, parse_request_body_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.errors import DatabaseError
from simcore_service_webserver.security.decorators import permission_required

from .._constants import RQ_PRODUCT_KEY, RQT_USERID_KEY
from .._meta import API_VTAG
from ..login.decorators import login_required
from ..utils_aiohttp import envelope_json_response
from . import _api

_logger = logging.getLogger(__name__)


routes = RouteTableDef()


class _RequestContext(RequestParams):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]
    product_name: str = Field(..., alias=RQ_PRODUCT_KEY)  # type: ignore[literal-required]


@routes.get(f"/{API_VTAG}/auth/api-keys", name="list_api_keys")
@login_required
@permission_required("user.apikey.*")
async def list_api_keys(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    api_keys_names = await _api.list_api_keys(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )
    return envelope_json_response(api_keys_names)


@routes.post(f"/{API_VTAG}/auth/api-keys", name="create_api_key")
@login_required
@permission_required("user.apikey.*")
async def create_api_key(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)
    new = await parse_request_body_as(ApiKeyCreate, request)
    try:
        data = await _api.create_api_key(
            request.app,
            new=new,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
    except DatabaseError as err:
        raise web.HTTPBadRequest(
            reason="Invalid API key name: already exists",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err

    return envelope_json_response(data)


@routes.delete(f"/{API_VTAG}/auth/api-keys", name="delete_api_key")
@login_required
@permission_required("user.apikey.*")
async def delete_api_key(request: web.Request):
    req_ctx = _RequestContext.parse_obj(request)

    # NOTE: SEE https://github.com/ITISFoundation/osparc-simcore/issues/4920
    body = await request.json()
    name = body.get("display_name")

    try:
        await _api.delete_api_key(
            request.app,
            name=name,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
    except DatabaseError as err:
        _logger.warning(
            "Failed to delete API key %s. Ignoring error", name, exc_info=err
        )

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
