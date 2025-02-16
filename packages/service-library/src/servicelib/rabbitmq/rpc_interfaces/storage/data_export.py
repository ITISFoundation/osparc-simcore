from typing import Final

from models_library.api_schemas_rpc_data_export.async_jobs import AsyncJobRpcGet
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.api_schemas_storage.data_export_async_jobs import (
    DataExportTaskStartInput,
)
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import NonNegativeInt, TypeAdapter

from ... import RabbitMQRPCClient

_DEFAULT_TIMEOUT_S: Final[NonNegativeInt] = 30

_RPC_METHOD_NAME_ADAPTER = TypeAdapter(RPCMethodName)


async def start_data_export(
    rabbitmq_rpc_client: RabbitMQRPCClient, *, paths: DataExportTaskStartInput
) -> AsyncJobRpcGet:
    result = await rabbitmq_rpc_client.request(
        STORAGE_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("start_data_export"),
        paths=paths,
        timeout_s=_DEFAULT_TIMEOUT_S,
    )
    assert isinstance(result, AsyncJobRpcGet)
    return result
