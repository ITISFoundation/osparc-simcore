import functools
import logging

from aiohttp import web
from pydantic import BaseModel
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler

from .._meta import API_VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _tokens
from ._handlers import UsersRequestContext
from .exceptions import TokenNotFoundError
from .schemas import TokenCreate

_logger = logging.getLogger(__name__)


routes = web.RouteTableDef()


def _handle_tokens_errors(handler: Handler):
    @functools.wraps(handler)
    async def _wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except TokenNotFoundError as exc:
            raise web.HTTPNotFound(
                reason=f"Token for {exc.service_id} not found"
            ) from exc

    return _wrapper


@routes.get(f"/{API_VTAG}/me/tokens", name="list_tokens")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def list_tokens(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    all_tokens = await _tokens.list_tokens(request.app, req_ctx.user_id)
    return envelope_json_response(all_tokens)


@routes.post(f"/{API_VTAG}/me/tokens", name="create_token")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def create_token(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    token_create = await parse_request_body_as(TokenCreate, request)
    await _tokens.create_token(request.app, req_ctx.user_id, token_create)
    return envelope_json_response(token_create, web.HTTPCreated)


class _TokenPathParams(BaseModel):
    service: str


@routes.get(f"/{API_VTAG}/me/tokens/{{service}}", name="get_token")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def get_token(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    req_path_params = parse_request_path_parameters_as(_TokenPathParams, request)
    token = await _tokens.get_token(
        request.app, req_ctx.user_id, req_path_params.service
    )
    return envelope_json_response(token)


@routes.delete(f"/{API_VTAG}/me/tokens/{{service}}", name="delete_token")
@login_required
@_handle_tokens_errors
@permission_required("user.tokens.*")
async def delete_token(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    req_path_params = parse_request_path_parameters_as(_TokenPathParams, request)
    await _tokens.delete_token(request.app, req_ctx.user_id, req_path_params.service)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
