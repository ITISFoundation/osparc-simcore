from pathlib import Path

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
    AsyncJobNameData,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.projects_nodes_io import LocationID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID

from ..._client_rpc import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit_job


async def compute_path_size(
    client: RabbitMQRPCClient,
    *,
    user_id: UserID,
    product_name: str,
    location_id: LocationID,
    path: Path,
) -> tuple[AsyncJobGet, AsyncJobNameData]:
    job_id_data = AsyncJobNameData(user_id=user_id, product_name=product_name)
    async_job_rpc_get = await submit_job(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=RPCMethodName("compute_path_size"),
        job_id_data=job_id_data,
        location_id=location_id,
        path=path,
    )
    return async_job_rpc_get, job_id_data
