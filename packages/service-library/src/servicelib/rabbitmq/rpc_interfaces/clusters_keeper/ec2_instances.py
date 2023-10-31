from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceType
from models_library.rabbitmq_basic_types import RPCMethodName

from ..._client_rpc import RabbitMQRPCClient
from ..._constants import RPC_REMOTE_METHOD_TIMEOUT_S


async def get_instance_type_details(
    client: RabbitMQRPCClient, *, instance_type_names: set[str]
) -> list[EC2InstanceType]:
    instance_types: list[EC2InstanceType] = await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_instance_type_details"),
        timeout_s=RPC_REMOTE_METHOD_TIMEOUT_S,
        instance_type_names=instance_type_names,
    )
    return instance_types
