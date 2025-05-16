from aiohttp import web
from fastapi import status
from models_library.api_schemas_webserver.functions import (
    Function,
    FunctionToRegister,
    RegisteredFunctionGet,
)
from pydantic import TypeAdapter
from servicelib.aiohttp.requests_validation import parse_request_path_parameters_as
from servicelib.rabbitmq import RPCRouter
from simcore_service_webserver.utils_aiohttp import envelope_json_response

from ..._meta import API_VTAG as VTAG
from .. import _functions_service
from ._functions_rest_exceptions import handle_rest_requests_exceptions
from ._functions_rest_schemas import FunctionPathParams

router = RPCRouter()

routes = web.RouteTableDef()


@routes.post(f"/{VTAG}/functions", name="register_function")
@handle_rest_requests_exceptions
async def register_function(request: web.Request) -> web.Response:
    function_to_register = TypeAdapter(FunctionToRegister).validate_python(
        await request.json()
    )

    registered_function = await _functions_service.register_function(
        app=request.app,
        function=TypeAdapter(Function).validate_python(function_to_register),
    )

    return envelope_json_response(
        TypeAdapter(RegisteredFunctionGet).validate_python(
            registered_function.model_dump(mode="json")
        )
    )


@routes.get(
    f"/{VTAG}/functions/{{function_id}}",
    name="get_function",
)
@handle_rest_requests_exceptions
async def get_function(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(FunctionPathParams, request)
    function_id = path_params.function_id

    registered_function = await _functions_service.get_function(
        app=request.app,
        function_id=function_id,
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
@handle_rest_requests_exceptions
async def delete_function(request: web.Request) -> web.Response:
    path_params = parse_request_path_parameters_as(FunctionPathParams, request)
    function_id = path_params.function_id

    await _functions_service.delete_function(
        app=request.app,
        function_id=function_id,
    )

    return web.Response(status=status.HTTP_204_NO_CONTENT)
