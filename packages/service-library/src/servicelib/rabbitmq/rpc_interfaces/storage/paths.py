from pathlib import Path

from models_library.api_schemas_rpc_async_jobs.async_jobs import (
    AsyncJobGet,
)
from models_library.api_schemas_storage import STORAGE_RPC_NAMESPACE
from models_library.projects_nodes_io import LocationID
from models_library.rabbitmq_basic_types import RPCMethodName
from models_library.users import UserID
from pydantic import TypeAdapter

from ....celery.models import OwnerMetadata
from ..._client_rpc import RabbitMQRPCClient
from ..async_jobs.async_jobs import submit


async def compute_path_size(
    client: RabbitMQRPCClient,
    *,
    location_id: LocationID,
    path: Path,
    owner_metadata: OwnerMetadata,
    user_id: UserID
) -> tuple[AsyncJobGet, OwnerMetadata]:
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python("compute_path_size"),
        owner_metadata=owner_metadata,
        location_id=location_id,
        path=path,
        user_id=user_id,
    )
    return async_job_rpc_get, owner_metadata


async def delete_paths(
    client: RabbitMQRPCClient,
    *,
    location_id: LocationID,
    paths: set[Path],
    owner_metadata: OwnerMetadata,
    user_id: UserID
) -> tuple[AsyncJobGet, OwnerMetadata]:
    async_job_rpc_get = await submit(
        rabbitmq_rpc_client=client,
        rpc_namespace=STORAGE_RPC_NAMESPACE,
        method_name=TypeAdapter(RPCMethodName).validate_python("delete_paths"),
        owner_metadata=owner_metadata,
        location_id=location_id,
        paths=paths,
        user_id=user_id,
    )
    return async_job_rpc_get, owner_metadata
