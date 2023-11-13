from dataclasses import asdict

from aws_library.ec2.models import EC2InstanceType
from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from servicelib.rabbitmq import RPCRouter

from ..modules.ec2 import get_ec2_client

router = RPCRouter()


@router.expose()
async def get_instance_type_details(
    app: FastAPI, *, instance_type_names: set[str]
) -> list[EC2InstanceTypeGet]:
    instance_capabilities: list[EC2InstanceType] = await get_ec2_client(
        app
    ).get_ec2_instance_capabilities(instance_type_names)
    return [EC2InstanceTypeGet(**asdict(t)) for t in instance_capabilities]
