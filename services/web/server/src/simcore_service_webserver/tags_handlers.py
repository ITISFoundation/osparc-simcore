import functools
from typing import Optional

from aiohttp import web
from models_library.users import UserID
from pydantic import BaseModel, Extra, Field, PositiveInt
from pydantic.color import Color
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowed,
    TagsRepo,
)

from .login.decorators import RQT_USERID_KEY, login_required
from .security_decorators import permission_required


def _handle_tags_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.Response:
        try:
            return await handler(request)

        except TagNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except TagOperationNotAllowed as exc:
            raise web.HTTPUnauthorized(reason=f"{exc}") from exc

    return wrapper


class RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)
    engine: str = Field(..., alias=APP_DB_ENGINE_KEY)


class TagPathParams(BaseModel):
    tag_id: PositiveInt

    class Config:
        allow_population_by_field_name = True
        extra = Extra.forbid


class TagUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class TagCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Color


@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def list_tags(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with req_ctx.engine.acquire() as conn:
        tags = await repo.list(conn)
        return tags


@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def update_tag(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_path_parameters_as(TagPathParams, request)
    tag_data = await parse_request_body_as(TagUpdate, request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with req_ctx.engine.acquire() as conn:
        tag = await repo.update(
            conn, query_params.tag_id, **tag_data.dict(exclude_unset=True)
        )
        return tag


@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def create_tag(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    tag_data = await parse_request_body_as(TagCreate, request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with req_ctx.engine.acquire() as conn:
        tag = await repo.create(
            conn,
            read=True,
            write=True,
            delete=True,
            **tag_data.dict(exclude_unset=True),
        )
        return tag


@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def delete_tag(request: web.Request):
    req_ctx = RequestContext.parse_obj(request)
    query_params = parse_request_path_parameters_as(TagPathParams, request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with req_ctx.engine.acquire() as conn:
        await repo.delete(conn, tag_id=query_params.tag_id)

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
