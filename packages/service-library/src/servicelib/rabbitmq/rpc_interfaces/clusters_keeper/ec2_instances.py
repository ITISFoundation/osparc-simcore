from typing import Literal

from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from models_library.rabbitmq_basic_types import RPCMethodName
from pydantic import TypeAdapter

from ..._client_rpc import RabbitMQRPCClient
from ..._constants import RPC_REMOTE_METHOD_TIMEOUT_S

_RPC_METHOD_NAME_ADAPTER: TypeAdapter[RPCMethodName] = TypeAdapter(RPCMethodName)


async def get_instance_type_details(
    client: RabbitMQRPCClient, *, instance_type_names: set[str] | Literal["ALL"]
) -> list[EC2InstanceTypeGet]:
    """**Remote method**

    Raises:
        InvalidEC2InstanceTypesRPCError -- some requested type name is not a valid
            EC2 instance type
        RPCServerError -- if anything else happens remotely

    """
    instance_types: list[EC2InstanceTypeGet] = await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        _RPC_METHOD_NAME_ADAPTER.validate_python("get_instance_type_details"),
        timeout_s=RPC_REMOTE_METHOD_TIMEOUT_S,
        instance_type_names=instance_type_names,
    )
    return instance_types
