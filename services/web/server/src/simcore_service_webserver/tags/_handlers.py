import functools

from aiohttp import web
from pydantic import parse_obj_as
from servicelib.aiohttp.db_asyncpg_engine import get_async_engine
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowedError,
    TagsRepo,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from .schemas import (
    TagCreate,
    TagGet,
    TagGroupCreate,
    TagGroupGet,
    TagGroupPathParams,
    TagPathParams,
    TagRequestContext,
    TagUpdate,
)


def _handle_tags_exceptions(handler: Handler):
    @functools.wraps(handler)
    async def wrapper(request: web.Request) -> web.StreamResponse:
        try:
            return await handler(request)

        except TagNotFoundError as exc:
            raise web.HTTPNotFound(reason=f"{exc}") from exc

        except TagOperationNotAllowedError as exc:
            raise web.HTTPUnauthorized(reason=f"{exc}") from exc

    return wrapper


routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/tags", name="create_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def create_tag(request: web.Request):
    assert request.app  # nosec
    engine: AsyncEngine = get_async_engine(request.app)
    req_ctx = TagRequestContext.parse_obj(request)
    new_tag = await parse_request_body_as(TagCreate, request)

    repo = TagsRepo(engine)
    tag = await repo.create(
        user_id=req_ctx.user_id,
        read=True,
        write=True,
        delete=True,
        **new_tag.dict(exclude_unset=True),
    )
    model = TagGet.from_db(tag)
    return envelope_json_response(model)


@routes.get(f"/{VTAG}/tags", name="list_tags")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def list_tags(request: web.Request):
    engine: AsyncEngine = get_async_engine(request.app)
    req_ctx = TagRequestContext.parse_obj(request)

    repo = TagsRepo(engine)
    tags = await repo.list_all(user_id=req_ctx.user_id)
    return envelope_json_response([TagGet.from_db(t).dict(by_alias=True) for t in tags])


@routes.patch(f"/{VTAG}/tags/{{tag_id}}", name="update_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def update_tag(request: web.Request):
    engine: AsyncEngine = get_async_engine(request.app)
    req_ctx = TagRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(TagPathParams, request)
    tag_updates = await parse_request_body_as(TagUpdate, request)

    repo = TagsRepo(engine)
    tag = await repo.update(
        user_id=req_ctx.user_id,
        tag_id=path_params.tag_id,
        **tag_updates.dict(exclude_unset=True),
    )
    model = TagGet.from_db(tag)
    return envelope_json_response(model)


@routes.delete(f"/{VTAG}/tags/{{tag_id}}", name="delete_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def delete_tag(request: web.Request):
    engine: AsyncEngine = get_async_engine(request.app)
    req_ctx = TagRequestContext.parse_obj(request)
    path_params = parse_request_path_parameters_as(TagPathParams, request)

    repo = TagsRepo(engine)
    await repo.delete(user_id=req_ctx.user_id, tag_id=path_params.tag_id)

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)


@routes.get(f"/{VTAG}/tags/{{tag_id}}/groups", name="list_tag_groups")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def list_tag_groups(request: web.Request):
    path_params = parse_request_path_parameters_as(TagPathParams, request)

    assert path_params  # nosec
    assert envelope_json_response(parse_obj_as(list[TagGroupGet], []))

    raise NotImplementedError


@routes.post(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="create_tag_group")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def create_tag_group(request: web.Request):
    path_params = parse_request_path_parameters_as(TagGroupPathParams, request)
    new_tag_group = await parse_request_body_as(TagGroupCreate, request)

    assert path_params  # nosec
    assert new_tag_group  # nosec

    raise NotImplementedError


@routes.put(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="replace_tag_groups")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def replace_tag_groups(request: web.Request):
    path_params = parse_request_path_parameters_as(TagGroupPathParams, request)
    new_tag_group = await parse_request_body_as(TagGroupCreate, request)

    assert path_params  # nosec
    assert new_tag_group  # nosec

    raise NotImplementedError


@routes.delete(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="delete_tag_group")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def delete_tag_group(request: web.Request):
    path_params = parse_request_path_parameters_as(TagGroupPathParams, request)

    assert path_params  # nosec
    assert web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
    raise NotImplementedError
