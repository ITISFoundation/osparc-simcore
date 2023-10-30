from models_library.api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceType
from models_library.rabbitmq_basic_types import RPCMethodName

from ....rabbitmq import RabbitMQRPCClient


async def get_instance_type_details(
    client: RabbitMQRPCClient, *, instance_type_names: set[str]
) -> list[EC2InstanceType]:
    return await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_instance_type_details"),
        instance_type_names=instance_type_names,
    )
