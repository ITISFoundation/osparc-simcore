from pydantic import AnyUrl, parse_obj_as
from simcore_service_clusters_keeper.models import EC2InstanceData


def get_gateway_url(ec2_instance: EC2InstanceData) -> AnyUrl:
    return parse_obj_as(AnyUrl, f"http://{ec2_instance.aws_public_ip}:8000")
