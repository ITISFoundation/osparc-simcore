from typing import Any

from aiohttp import web
from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionToRegister,
    RegisteredFunction,
    RegisteredFunctionGet,
    RegisteredFunctionUpdate,
)
from models_library.api_schemas_webserver.users import MyFunctionPermissionsGet
from models_library.functions import (
    FunctionAccessRights,
    FunctionClass,
    FunctionID,
    RegisteredProjectFunction,
    RegisteredSolverFunction,
)
from models_library.products import ProductName
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    handle_validation_as_http_error,
    parse_request_path_parameters_as,
    parse_request_query_parameters_as,
)

from ..._meta import API_VTAG as VTAG
from ...login.decorators import login_required
from ...models import AuthenticatedRequestContext
from ...projects import _projects_service
from ...projects.models import ProjectDBGet
from ...security.decorators import permission_required
from ...utils_aiohttp import create_json_response_from_page, envelope_json_response
from .. import _functions_service
from .._services_metadata import proxy as _services_metadata_proxy
from .._services_metadata.proxy import ServiceMetadata
from ._functions_rest_exceptions import handle_rest_requests_exceptions
from ._functions_rest_schemas import (
    FunctionGetQueryParams,
    FunctionPathParams,
    FunctionsListQueryParams,
)

routes = web.RouteTableDef()


async def _build_function_access_rights(
    app: web.Application,
    user_id: UserID,
    product_name: ProductName,
    function_id: FunctionID,
) -> FunctionAccessRights:
    access_rights = await _functions_service.get_function_user_permissions(
        app=app,
        user_id=user_id,
        product_name=product_name,
        function_id=function_id,
    )

    return FunctionAccessRights(
        read=access_rights.read,
        write=access_rights.write,
        execute=access_rights.execute,
    )


def _build_project_function_extras_dict(
    project: ProjectDBGet,
) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    if thumbnail := project.thumbnail:
        extras["thumbnail"] = thumbnail
    return extras


def _build_solver_function_extras_dict(
    service_metadata: ServiceMetadata,
) -> dict[str, Any]:

    extras: dict[str, Any] = {}
    if thumbnail := service_metadata.thumbnail:
        extras["thumbnail"] = thumbnail
    return extras


async def _build_function_extras(
    app: web.Application, *, function: RegisteredFunction
) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    match function.function_class:
        case FunctionClass.PROJECT:
            assert isinstance(function, RegisteredProjectFunction)
            projects = await _projects_service.batch_get_projects(
                app=app,
                project_uuids=[function.project_id],
            )
            if project := projects.get(function.project_id):
                extras |= _build_project_function_extras_dict(
                    project=project,
                )
        case FunctionClass.SOLVER:
            assert isinstance(function, RegisteredSolverFunction)
            services_metadata = await _services_metadata_proxy.get_service_metadata(
                app,
                key=function.solver_key,
                version=function.solver_version,
            )
            extras |= _build_solver_function_extras_dict(
                service_metadata=services_metadata,
            )
    return extras


@routes.post(f"/{VTAG}/functions", name="register_function")
@login_required
@handle_rest_requests_exceptions
async def register_function(request: web.Request) -> web.Response:
    with handle_validation_as_http_error(
        error_msg_template="Invalid parameter/s '{failed}' in request path",
        resource_name=request.rel_url.path,
    ):
        function_to_register: FunctionToRegister = TypeAdapter(
            FunctionToRegister
        ).validate_python(await request.json())

    req_ctx = AuthenticatedRequestContext.model_validate(request)
    registered_function: RegisteredFunction = (
        await _functions_service.register_function(
            app=request.app,
            function=TypeAdapter(Function).validate_python(function_to_register),
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
    )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            registered_function.model_dump(mode="json")
        ),
        web.HTTPCreated,
    )


@routes.get(
    f"/{VTAG}/functions",
    name="list_functions",
)
@login_required
@permission_required("function.read")
@handle_rest_requests_exceptions
async def list_functions(request: web.Request) -> web.Response:
    query_params: FunctionsListQueryParams = parse_request_query_parameters_as(
        FunctionsListQueryParams, request
    )

    req_ctx = AuthenticatedRequestContext.model_validate(request)
    functions, page_meta_info = await _functions_service.list_functions(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        pagination_limit=query_params.limit,
        pagination_offset=query_params.offset,
    )

    chunk: list[RegisteredFunctionGet] = []

    extras_map: dict[FunctionID, dict[str, Any]] = {}

    if query_params.include_extras:
        if any(
            function.function_class == FunctionClass.PROJECT for function in functions
        ):
            project_uuids = [
                function.project_id
                for function in functions
                if function.function_class == FunctionClass.PROJECT
            ]
            projects_cache = await _projects_service.batch_get_projects(
                request.app,
                project_uuids=project_uuids,
            )
            for function in functions:
                if function.function_class == FunctionClass.PROJECT:
                    project = projects_cache.get(function.project_id)
                    if not project:
                        continue
                    extras_map[function.uid] = _build_project_function_extras_dict(
                        project=project
                    )

        if any(
            function.function_class == FunctionClass.SOLVER for function in functions
        ):
            service_keys_and_versions = {
                (function.solver_key, function.solver_version)
                for function in functions
                if function.function_class == FunctionClass.SOLVER
            }
            service_metadata_cache = (
                await _services_metadata_proxy.batch_get_service_metadata(
                    app=request.app, keys_and_versions=service_keys_and_versions
                )
            )
            for function in functions:
                if function.function_class == FunctionClass.SOLVER:
                    service_metadata = service_metadata_cache.get(
                        (function.solver_key, function.solver_version)
                    )
                    if not service_metadata:
                        continue
                    extras_map[function.uid] = _build_solver_function_extras_dict(
                        service_metadata=service_metadata
                    )

    for function in functions:
        access_rights = await _build_function_access_rights(
            request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
            function_id=function.uid,
        )

        extras = extras_map.get(function.uid, {})

        chunk.append(
            TypeAdapter(RegisteredFunctionGet).validate_python(
                function.model_dump() | {"access_rights": access_rights, **extras}
            )
        )

    page = Page[RegisteredFunctionGet].model_validate(
        paginate_data(
            chunk=chunk,
            request_url=request.url,
            total=page_meta_info.total,
            limit=query_params.limit,
            offset=query_params.offset,
        )
    )
    return create_json_response_from_page(page)


@routes.get(
    f"/{VTAG}/functions/{{function_id}}",
    name="get_function",
)
@login_required
@permission_required("function.read")
@handle_rest_requests_exceptions
async def get_function(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(FunctionPathParams, request)
    function_id = path_params.function_id

    query_params: FunctionGetQueryParams = parse_request_query_parameters_as(
        FunctionGetQueryParams, request
    )

    req_ctx = AuthenticatedRequestContext.model_validate(request)
    function = await _functions_service.get_function(
        app=request.app,
        function_id=function_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    access_rights = await _build_function_access_rights(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        function_id=function_id,
    )

    extras = (
        await _build_function_extras(request.app, function=function)
        if query_params.include_extras
        else {}
    )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            function.model_dump() | {"access_rights": access_rights, **extras}
        )
    )


@routes.patch(
    f"/{VTAG}/functions/{{function_id}}",
    name="update_function",
)
@login_required
@permission_required("function.update")
@handle_rest_requests_exceptions
async def update_function(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(FunctionPathParams, request)
    function_id = path_params.function_id

    query_params: FunctionGetQueryParams = parse_request_query_parameters_as(
        FunctionGetQueryParams, request
    )

    function_update = TypeAdapter(RegisteredFunctionUpdate).validate_python(
        await request.json()
    )
    req_ctx = AuthenticatedRequestContext.model_validate(request)

    function = await _functions_service.update_function(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        function_id=function_id,
        function=function_update,
    )

    access_rights = await _build_function_access_rights(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        function_id=function_id,
    )

    extras = (
        await _build_function_extras(request.app, function=function)
        if query_params.include_extras
        else {}
    )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            function.model_dump() | {"access_rights": access_rights, **extras}
        )
    )


@routes.delete(
    f"/{VTAG}/functions/{{function_id}}",
    name="delete_function",
)
@login_required
@permission_required("function.delete")
@handle_rest_requests_exceptions
async def delete_function(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(FunctionPathParams, request)
    function_id = path_params.function_id
    req_ctx = AuthenticatedRequestContext.model_validate(request)
    await _functions_service.delete_function(
        app=request.app,
        function_id=function_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# /me/* endpoints
#


@routes.get(f"/{VTAG}/me/function-permissions", name="list_user_functions_permissions")
@login_required
@handle_rest_requests_exceptions
async def list_user_functions_permissions(request: web.Request) -> web.Response:
    req_ctx = AuthenticatedRequestContext.model_validate(request)

    function_permissions = (
        await _functions_service.get_functions_user_api_access_rights(
            app=request.app,
            user_id=req_ctx.user_id,
            product_name=req_ctx.product_name,
        )
    )

    assert function_permissions.user_id == req_ctx.user_id  # nosec

    return envelope_json_response(
        MyFunctionPermissionsGet(
            read_functions=function_permissions.read_functions,
            write_functions=function_permissions.write_functions,
        )
    )
