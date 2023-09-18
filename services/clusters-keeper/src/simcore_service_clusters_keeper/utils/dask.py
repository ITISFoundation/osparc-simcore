from pydantic import AnyUrl, parse_obj_as

from ..models import EC2InstanceData


def get_scheduler_url(ec2_instance: EC2InstanceData) -> AnyUrl:
    url: AnyUrl = parse_obj_as(AnyUrl, f"tcp://{ec2_instance.aws_public_ip}:8786")
    return url
