from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceType
from servicelib.rabbitmq import RPCRouter

from ..modules.ec2 import get_ec2_client

router = RPCRouter()


@router.expose()
async def get_instance_type_details(
    app: FastAPI, *, instance_type_names: set[str]
) -> list[EC2InstanceType]:
    instance_capabilities: list[EC2InstanceType] = await get_ec2_client(
        app
    ).get_ec2_instance_capabilities(instance_type_names)
    return instance_capabilities
