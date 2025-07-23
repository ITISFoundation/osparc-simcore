from typing import Annotated

from fastapi import Depends
from models_library.functions import (
    FunctionJob,
    FunctionJobID,
    FunctionJobStatus,
    FunctionOutputs,
    RegisteredFunction,
)
from models_library.products import ProductName
from models_library.users import UserID
from simcore_service_api_server.api.dependencies.authentication import (
    get_current_user_id,
    get_product_name,
)
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


async def get_stored_job_outputs(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> FunctionOutputs:

    return await wb_api_rpc.get_function_job_outputs(
        function_job_id=function_job_id, user_id=user_id, product_name=product_name
    )


async def get_function_job_dependency(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> FunctionJob:
    return await wb_api_rpc.get_function_job(
        function_job_id=function_job_id, user_id=user_id, product_name=product_name
    )


async def get_function_from_functionjob(
    function_job: Annotated[FunctionJob, Depends(get_function_job_dependency)],
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> RegisteredFunction:
    return await wb_api_rpc.get_function(
        function_id=function_job.function_uid,
        user_id=user_id,
        product_name=product_name,
    )


async def get_stored_job_status(
    function_job_id: FunctionJobID,
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
) -> FunctionJobStatus:
    return await wb_api_rpc.get_function_job_status(
        function_job_id=function_job_id, user_id=user_id, product_name=product_name
    )
