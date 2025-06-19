from aiohttp import web
from common_library.user_messages import user_message
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
    parse_request_path_parameters_as,
)
from simcore_postgres_database.utils_tags import (
    TagNotFoundError,
    TagOperationNotAllowedError,
)

from .._meta import API_VTAG as VTAG
from ..exception_handling import (
    ExceptionToHttpErrorMap,
    HttpErrorInfo,
    exception_handling_decorator,
    to_exceptions_handlers_map,
)
from ..login.decorators import login_required
from ..security.decorators import permission_required
from ..utils_aiohttp import envelope_json_response
from . import _service
from .errors import (
    InsufficientTagShareAccessError,
    ShareTagWithEveryoneNotAllowedError,
    ShareTagWithProductGroupNotAllowedError,
)
from .schemas import (
    TagCreate,
    TagGroupCreate,
    TagGroupGet,
    TagGroupPathParams,
    TagPathParams,
    TagRequestContext,
    TagUpdate,
)

_TO_HTTP_ERROR_MAP: ExceptionToHttpErrorMap = {
    TagNotFoundError: HttpErrorInfo(
        status.HTTP_404_NOT_FOUND,
        user_message("Tag {tag_id} not found: either no access or does not exists"),
    ),
    TagOperationNotAllowedError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Could not {operation} tag {tag_id}. Not found or insuficient access."
        ),
    ),
    ShareTagWithEveryoneNotAllowedError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Sharing with everyone is not permitted."),
    ),
    ShareTagWithProductGroupNotAllowedError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message(
            "Sharing with all users is only permitted to admin users (e.g. testers, POs, ...)."
        ),
    ),
    InsufficientTagShareAccessError: HttpErrorInfo(
        status.HTTP_403_FORBIDDEN,
        user_message("Insufficient access rightst to share (or unshare) tag {tag_id}."),
    ),
}


_handle_tags_exceptions = exception_handling_decorator(
    to_exceptions_handlers_map(_TO_HTTP_ERROR_MAP)
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
    return envelope_json_response(created, status_cls=web.HTTPCreated)


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
    req_ctx = TagRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(TagPathParams, request)

    got = await _service.list_tag_groups(
        request.app,
        caller_user_id=req_ctx.user_id,
        tag_id=path_params.tag_id,
    )
    return envelope_json_response([TagGroupGet.from_domain_model(md) for md in got])


@routes.post(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="create_tag_group")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def create_tag_group(request: web.Request):
    req_ctx = TagRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(TagGroupPathParams, request)
    body_params = await parse_request_body_as(TagGroupCreate, request)

    got = await _service.share_tag_with_group(
        request.app,
        caller_user_id=req_ctx.user_id,
        tag_id=path_params.tag_id,
        group_id=path_params.group_id,
        access_rights=body_params.to_domain_model(),
    )

    return envelope_json_response(
        TagGroupGet.from_domain_model(got), status_cls=web.HTTPCreated
    )


@routes.put(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="replace_tag_group")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def replace_tag_group(request: web.Request):
    req_ctx = TagRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(TagGroupPathParams, request)
    body_params = await parse_request_body_as(TagGroupCreate, request)

    got = await _service.share_tag_with_group(
        request.app,
        caller_user_id=req_ctx.user_id,
        tag_id=path_params.tag_id,
        group_id=path_params.group_id,
        access_rights=body_params.to_domain_model(),
    )

    return envelope_json_response(TagGroupGet.from_domain_model(got))


@routes.delete(f"/{VTAG}/tags/{{tag_id}}/groups/{{group_id}}", name="delete_tag_group")
@login_required
@permission_required("tag.crud.*")
@_handle_tags_exceptions
async def delete_tag_group(request: web.Request):
    req_ctx = TagRequestContext.model_validate(request)
    path_params = parse_request_path_parameters_as(TagGroupPathParams, request)

    await _service.unshare_tag_with_group(
        request.app,
        caller_user_id=req_ctx.user_id,
        tag_id=path_params.tag_id,
        group_id=path_params.group_id,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)
