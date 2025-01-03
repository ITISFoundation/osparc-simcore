from aiohttp import web
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowedError,
)

from .._meta import API_VTAG as VTAG
from ..exception_handling import (
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _service
from .schemas import (
    TagCreate,
    TagGroupCreate,
    TagGroupGet,
    TagGroupPathParams,
    TagPathParams,
    TagRequestContext,
    TagUpdate,
)

_handle_tags_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(
        {
            TagNotFoundError: HttpErrorInfo(
                status.HTTP_404_NOT_FOUND,
                "Tag {tag_id} not found: either no access or does not exists",
            ),
            TagOperationNotAllowedError: HttpErrorInfo(
                status.HTTP_403_FORBIDDEN,
                "Could not {operation} tag {tag_id}. Not found or insuficient access.",
            ),
        }
    )
)


routes = web.RouteTableDef()

#
# tags CRUD standard operations
#


@routes.post(f"/{VTAG}/tags", name="create_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def create_tag(request: web.Request):
    assert request.app  # nosec
    req_ctx = TagRequestContext.model_validate(request)
    new_tag = await parse_request_body_as(TagCreate, request)

    created = await _service.create_tag(
        request.app, user_id=req_ctx.user_id, new_tag=new_tag
    )
    return envelope_json_response(created)


@routes.get(f"/{VTAG}/tags", name="list_tags")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def list_tags(request: web.Request):

    req_ctx = TagRequestContext.model_validate(request)
    got = await _service.list_tags(request.app, user_id=req_ctx.user_id)
    return envelope_json_response(got)


@routes.patch(f"/{VTAG}/tags/{{tag_id}}", name="update_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def update_tag(request: web.Request):
    req_ctx = TagRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(TagPathParams, request)
    tag_updates = await parse_request_body_as(TagUpdate, request)

    updated = await _service.update_tag(
        request.app,
        user_id=req_ctx.user_id,
        tag_id=path_params.tag_id,
        tag_updates=tag_updates,
    )
    return envelope_json_response(updated)


@routes.delete(f"/{VTAG}/tags/{{tag_id}}", name="delete_tag")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def delete_tag(request: web.Request):
    req_ctx = TagRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(TagPathParams, request)

    await _service.delete_tag(
        request.app, user_id=req_ctx.user_id, tag_id=path_params.tag_id
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# tags ACCESS RIGHTS is exposed as a sub-resource groups
#


@routes.get(f"/{VTAG}/tags/{{tag_id}}/groups", name="list_tag_groups")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def list_tag_groups(request: web.Request):
    path_params = parse_request_path_parameters_as(TagPathParams, request)

    assert path_params  # nosec
    assert envelope_json_response(TypeAdapter(list[TagGroupGet]).validate_python([]))

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


@routes.put(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="replace_tag_group")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def replace_tag_group(request: web.Request):
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
