from dataclasses import dataclass

from pydantic import ByteSize, PositiveInt

from ..api_schemas_clusters_keeper import CLUSTERS_KEEPER_RPC_NAMESPACE
from ..rabbitmq_basic_types import RPCMethodName, RPCProtocol


@dataclass(frozen=True)
class EC2InstanceType:
    name: str
    cpus: PositiveInt
    ram: ByteSize


async def get_instance_type_details(
    client: RPCProtocol, *, instance_type_names: set[str]
) -> list[EC2InstanceType]:
    return await client.request(
        CLUSTERS_KEEPER_RPC_NAMESPACE,
        RPCMethodName("get_instance_type_details"),
        instance_type_names=instance_type_names,
    )
