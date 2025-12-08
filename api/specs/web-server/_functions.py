# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.functions import (
    FunctionGroupAccessRightsGet,
    FunctionGroupAccessRightsUpdate,
    FunctionToRegister,
    RegisteredFunctionGet,
    RegisteredFunctionUpdate,
)
from models_library.generics import Envelope
from models_library.groups import GroupID
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.functions._controller._functions_rest import (
    FunctionGroupPathParams,
)
from simcore_service_webserver.functions._controller._functions_rest_schemas import (
    FunctionDeleteQueryParams,
    FunctionGetQueryParams,
    FunctionPathParams,
    FunctionsListQueryParams,
)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "functions",
    ],
)


@router.post(
    "/functions",
    response_model=Envelope[RegisteredFunctionGet],
)
async def register_function(
    _body: FunctionToRegister,
) -> Envelope[RegisteredFunctionGet]: ...


@router.get(
    "/functions",
    response_model=Envelope[list[RegisteredFunctionGet]],
)
async def list_functions(
    _query: Annotated[as_query(FunctionsListQueryParams), Depends()],
): ...


@router.get(
    "/functions/{function_id}",
    response_model=Envelope[RegisteredFunctionGet],
)
async def get_function(
    _path: Annotated[FunctionPathParams, Depends()],
    _query: Annotated[as_query(FunctionGetQueryParams), Depends()],
): ...


@router.patch(
    "/functions/{function_id}",
    response_model=Envelope[RegisteredFunctionGet],
)
async def update_function(
    _body: RegisteredFunctionUpdate,
    _path: Annotated[FunctionPathParams, Depends()],
): ...


@router.delete(
    "/functions/{function_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_function(
    _path: Annotated[FunctionPathParams, Depends()],
    _query: Annotated[as_query(FunctionDeleteQueryParams), Depends()],
): ...


@router.get(
    "/functions/{function_id}/groups",
    response_model=Envelope[dict[GroupID, FunctionGroupAccessRightsGet]],
)
async def get_function_groups(
    _path: Annotated[FunctionPathParams, Depends()],
): ...


@router.put(
    "/functions/{function_id}/groups/{group_id}",
    summary="Create or update a Function Group",
    response_model=Envelope[FunctionGroupAccessRightsGet],
)
async def create_or_update_function_group(
    _path: Annotated[FunctionGroupPathParams, Depends()],
    _body: FunctionGroupAccessRightsUpdate,
): ...


@router.delete(
    "/functions/{function_id}/groups/{group_id}",
    summary="Delete a Function Group",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_function_group(
    _path: Annotated[FunctionGroupPathParams, Depends()],
): ...
