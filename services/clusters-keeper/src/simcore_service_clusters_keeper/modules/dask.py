from ..models import EC2InstanceData


async def ping_gateway(ec2_instance: EC2InstanceData) -> bool:
    return False
