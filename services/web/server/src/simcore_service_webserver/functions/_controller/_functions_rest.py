from aiohttp import web
from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionToRegister,
    RegisteredFunction,
    RegisteredFunctionGet,
)
from models_library.api_schemas_webserver.users import MyFunctionPermissionsGet
from pydantic import TypeAdapter
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    handle_validation_as_http_error,
    parse_request_path_parameters_as,
)

from ..._meta import API_VTAG as VTAG
from ...login.decorators import login_required
from ...models import AuthenticatedRequestContext
from ...security.decorators import permission_required
from ...utils_aiohttp import envelope_json_response
from .. import _functions_service
from ._functions_rest_exceptions import handle_rest_requests_exceptions
from ._functions_rest_schemas import FunctionPathParams

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
    f"/{VTAG}/functions/{{function_id}}",
    name="get_function",
)
@login_required
@permission_required("function.read")
@handle_rest_requests_exceptions
async def get_function(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(FunctionPathParams, request)
    function_id = path_params.function_id

    req_ctx = AuthenticatedRequestContext.model_validate(request)
    registered_function: RegisteredFunction = await _functions_service.get_function(
        app=request.app,
        function_id=function_id,
        user_id=req_ctx.user_id,
        product_name=req_ctx.product_name,
    )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            registered_function.model_dump(mode="json")
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
        MyFunctionPermissionsGet(write_functions=function_permissions.write_functions)
    )
