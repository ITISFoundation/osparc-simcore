from typing import Annotated

from fastapi import APIRouter, Depends
from simcore_service_api_server.api.dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient

router = APIRouter()


@router.post("/ping")
async def ping(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.ping()
