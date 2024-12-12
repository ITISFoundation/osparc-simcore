from typing import Annotated, cast

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ...services_rpc.wb_api_server import WbApiRpcClient


async def get_wb_api_rpc_client(
    app: Annotated[FastAPI, Depends(get_app)]
) -> WbApiRpcClient:
    assert app.state.wb_api_rpc_client  # nosec
    return cast(WbApiRpcClient, app.state.wb_api_rpc_client)
