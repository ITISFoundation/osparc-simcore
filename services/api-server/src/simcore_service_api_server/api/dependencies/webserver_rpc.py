from fastapi import FastAPI
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


def get_wb_api_rpc_client(app: FastAPI) -> WbApiRpcClient:
    assert app.state.wb_api_rpc_client  # nosec
    return app.state.wb_api_rpc_client
