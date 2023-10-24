import logging
import uuid as uuidlib
from typing import TypedDict

from aiohttp import web
from aiohttp.web import RouteTableDef
from models_library.api_schemas_webserver.auth import ApiKeyCreate, ApiKeyGet
from servicelib.aiohttp.requests_validation import parse_request_body_as
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.errors import DatabaseError

from ..security.api import check_permission
from ._api_keys_db import ApiKeyRepo
from .decorators import login_required
from .utils import get_random_string

_logger = logging.getLogger(__name__)


class ApiCredentials(TypedDict):
    api_key: str
    api_secret: str


def _get_random_uuid_string() -> str:
    return uuidlib.uuid5(uuidlib.NAMESPACE_DNS, get_random_string(20)).hex


def _generate_api_credentials() -> ApiCredentials:
    return ApiCredentials(
        api_key=_get_random_uuid_string(), api_secret=_get_random_uuid_string()
    )


#
# HANDLERS
#


routes = RouteTableDef()


@routes.get("/v0/auth/api-keys", name="list_api_keys")
@login_required
async def list_api_keys(request: web.Request):
    await check_permission(request, "user.apikey.*")

    crud = ApiKeyRepo.create_from_request(request)
    return await crud.list_names()


@routes.post("/v0/auth/api-keys", name="create_api_key")
@login_required
async def create_api_key(request: web.Request):
    await check_permission(request, "user.apikey.*")

    api_key = await parse_request_body_as(ApiKeyCreate, request)
    credentials = _generate_api_credentials()
    try:
        repo = ApiKeyRepo.create_from_request(request)
        await repo.create(api_key, **credentials)
    except DatabaseError as err:
        raise web.HTTPBadRequest(
            reason="Invalid API key name: already exists",
            content_type=MIMETYPE_APPLICATION_JSON,
        ) from err

    return ApiKeyGet(
        display_name=api_key.display_name,
        api_key=credentials["api_key"],
        api_secret=credentials["api_secret"],
    ).dict(**RESPONSE_MODEL_POLICY)


@routes.delete("/v0/auth/api-keys", name="delete_api_key")
@login_required
async def delete_api_key(request: web.Request):
    await check_permission(request, "user.apikey.*")

    body = await request.json()
    display_name = body.get("display_name")

    try:
        repo = ApiKeyRepo.create_from_request(request)
        await repo.delete(display_name)
    except DatabaseError as err:
        _logger.warning(
            "Failed to delete API key %s. Ignoring error", display_name, exc_info=err
        )

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
