import functools
import re

from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.users import UserID
from pydantic import BaseModel, ConstrainedStr, Extra, Field, PositiveInt
from servicelib.aiohttp.application_keys import APP_DB_ENGINE_KEY
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.aiohttp.typing_extension import Handler
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from simcore_postgres_database.utils_tags import (
    TagDict,
    TagNotFoundError,
    TagOperationNotAllowedError,
    TagsRepo,
)

from .._meta import API_VTAG as VTAG
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response


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


#
# API components/schemas
#


class _RequestContext(BaseModel):
    user_id: UserID = Field(..., alias=RQT_USERID_KEY)  # type: ignore[literal-required]


class _InputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = False
        extra = Extra.forbid
        allow_mutations = False


class ColorStr(ConstrainedStr):
    regex = re.compile(r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$")


class TagPathParams(_InputSchema):
    tag_id: PositiveInt


class TagUpdate(_InputSchema):
    name: str | None = None
    description: str | None = None
    color: ColorStr | None = None


class TagCreate(_InputSchema):
    name: str
    description: str | None = None
    color: ColorStr


class _OutputSchema(BaseModel):
    class Config:
        allow_population_by_field_name = True
        extra = Extra.ignore
        allow_mutations = False


class TagAccessRights(_OutputSchema):
    # NOTE: analogous to GroupAccessRights
    read: bool
    write: bool
    delete: bool


class TagGet(_OutputSchema):
    id: PositiveInt
    name: str
    description: str | None = None
    color: str

    # analogous to UsersGroup
    access_rights: TagAccessRights = Field(..., alias="accessRights")

    @classmethod
    def from_db(cls, tag: TagDict) -> "TagGet":
        # NOTE: cls(access_rights=tag, **tag) would also work because of Config
        return cls(
            id=tag["id"],
            name=tag["name"],
            description=tag["description"],
            color=tag["color"],
            access_rights=TagAccessRights(  # type: ignore[call-arg]
                read=tag["read"],
                write=tag["write"],
                delete=tag["delete"],
            ),
        )


#
# API handlers
#

routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/tags", name="create_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def create_tag(request: web.Request):
    engine: Engine = request.app[APP_DB_ENGINE_KEY]
    req_ctx = _RequestContext.parse_obj(request)
    tag_data = await parse_request_body_as(TagCreate, request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with engine.acquire() as conn:
        tag = await repo.create(
            conn,
            read=True,
            write=True,
            delete=True,
            **tag_data.dict(exclude_unset=True),
        )
        model = TagGet.from_db(tag)
        return envelope_json_response(model)


@routes.get(f"/{VTAG}/tags", name="list_tags")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def list_tags(request: web.Request):
    engine: Engine = request.app[APP_DB_ENGINE_KEY]
    req_ctx = _RequestContext.parse_obj(request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with engine.acquire() as conn:
        tags = await repo.list_all(conn)
        return envelope_json_response(
            [TagGet.from_db(t).dict(by_alias=True) for t in tags]
        )


@routes.patch(f"/{VTAG}/tags/{{tag_id}}", name="update_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def update_tag(request: web.Request):
    engine: Engine = request.app[APP_DB_ENGINE_KEY]
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_path_parameters_as(TagPathParams, request)
    tag_data = await parse_request_body_as(TagUpdate, request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with engine.acquire() as conn:
        tag = await repo.update(
            conn, query_params.tag_id, **tag_data.dict(exclude_unset=True)
        )
        model = TagGet.from_db(tag)
        return envelope_json_response(model)


@routes.delete(f"/{VTAG}/tags/{{tag_id}}", name="delete_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def delete_tag(request: web.Request):
    engine: Engine = request.app[APP_DB_ENGINE_KEY]
    req_ctx = _RequestContext.parse_obj(request)
    query_params = parse_request_path_parameters_as(TagPathParams, request)

    repo = TagsRepo(user_id=req_ctx.user_id)
    async with engine.acquire() as conn:
        await repo.delete(conn, tag_id=query_params.tag_id)

    raise web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)
