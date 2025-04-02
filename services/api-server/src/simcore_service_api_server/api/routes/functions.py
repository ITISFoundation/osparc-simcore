from typing import Annotated

from fastapi import APIRouter, Depends

from ...services_rpc.wb_api_server import WbApiRpcClient
from ..dependencies.webserver_rpc import (
    get_wb_api_rpc_client,
)

router = APIRouter()


@router.post("/ping", include_in_schema=False)
async def ping(
    wb_api_rpc: Annotated[WbApiRpcClient, Depends(get_wb_api_rpc_client)],
):
    return await wb_api_rpc.ping()
