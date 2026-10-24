from typing import Literal

from aws_library.ec2 import EC2InstanceType
from aws_library.ec2._errors import EC2InstanceTypeInvalidError
from fastapi import FastAPI
from models_library.api_schemas_clusters_keeper.ec2_instances import EC2InstanceTypeGet
from servicelib.rabbitmq import RPCRouter
from servicelib.rabbitmq.rpc_interfaces.clusters_keeper.errors import InvalidEC2InstanceTypesRPCError

from ..modules.ec2 import get_ec2_client

router = RPCRouter()


@router.expose(reraise_if_error_type=(InvalidEC2InstanceTypesRPCError,))
async def get_instance_type_details(
    app: FastAPI, *, instance_type_names: set[str] | Literal["ALL"]
) -> list[EC2InstanceTypeGet]:
    """Raises: InvalidEC2InstanceTypesRPCError -- some requested type name is not a
    valid EC2 instance type

    """
    try:
        instance_capabilities: list[EC2InstanceType] = await get_ec2_client(app).get_ec2_instance_capabilities(
            instance_type_names
        )
    except EC2InstanceTypeInvalidError as exc:
        ec2_types = instance_type_names if instance_type_names != "ALL" else set()
        raise InvalidEC2InstanceTypesRPCError(ec2_types=ec2_types) from exc
    return [EC2InstanceTypeGet(name=t.name, cpus=t.resources.cpus, ram=t.resources.ram) for t in instance_capabilities]
