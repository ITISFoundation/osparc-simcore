from aiohttp import web
from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionToRegister,
    RegisteredFunction,
    RegisteredFunctionGet,
    RegisteredFunctionUpdate,
    RegisteredProjectFunctionGet,
)
from models_library.api_schemas_webserver.users import MyFunctionPermissionsGet
from models_library.functions import FunctionClass, RegisteredProjectFunction
from models_library.rest_pagination import Page
from models_library.rest_pagination_utils import paginate_data
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
from ._functions_rest_exceptions import handle_rest_requests_exceptions
from ._functions_rest_schemas import (
    FunctionGetQueryParams,
    FunctionPathParams,
    FunctionsListQueryParams,
)

routes = web.RouteTableDef()


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
    projects_map: dict[str, ProjectDBGet | None] = (
        {}
    )  # ProjectDBGet has to be renamed at some point!

    if query_params.include_extras:
        project_ids = []
        for function in functions:
            if function.function_class == FunctionClass.PROJECT:
                assert isinstance(function, RegisteredProjectFunction)
                project_ids.append(function.project_id)

        projects_map = {
            f"{p.uuid}": p
            for p in await _projects_service.batch_get_projects(
                request.app,
                project_uuids=project_ids,
            )
        }

    for function in functions:
        if (
            query_params.include_extras
            and function.function_class == FunctionClass.PROJECT
        ):
            assert isinstance(function, RegisteredProjectFunction)  # nosec
            if project := projects_map.get(f"{function.project_id}"):
                chunk.append(
                    TypeAdapter(RegisteredProjectFunctionGet).validate_python(
                        function.model_dump(mode="json")
                        | {
                            "thumbnail": (
                                f"{project.thumbnail}" if project.thumbnail else None
                            ),
                        }
                    )
                )
        else:
            chunk.append(
                TypeAdapter(RegisteredFunctionGet).validate_python(
                    function.model_dump(mode="json")
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
    registered_function: RegisteredFunction = await _functions_service.get_function(
        app=request.app,
        function_id=function_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    if (
        query_params.include_extras
        and registered_function.function_class == FunctionClass.PROJECT
    ):
        assert isinstance(registered_function, RegisteredProjectFunctionGet)  # nosec

        project_dict = await _projects_service.get_project_for_user(
            app=request.app,
            project_uuid=f"{registered_function.project_id}",
            user_id=req_ctx.user_id,
        )

        return envelope_json_response(
            TypeAdapter(RegisteredProjectFunctionGet).validate_python(
                registered_function.model_dump(mode="json")
                | {
                    "thumbnail": project_dict.get("thumbnail", None),
                }
            )
        )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            registered_function.model_dump(mode="json")
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

    function_update = TypeAdapter(RegisteredFunctionUpdate).validate_python(
        await request.json()
    )
    req_ctx = AuthenticatedRequestContext.model_validate(request)

    updated_function = await _functions_service.update_function(
        request.app,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
        function_id=function_id,
        function=function_update,
    )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            updated_function.model_dump(mode="json")
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
