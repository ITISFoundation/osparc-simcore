from models_library.clusters import SimpleAuthentication
from models_library.users import UserID
from pydantic import AnyUrl, SecretStr, parse_obj_as

from ..models import EC2InstanceData


def get_gateway_url(ec2_instance: EC2InstanceData) -> AnyUrl:
    return parse_obj_as(AnyUrl, f"http://{ec2_instance.aws_public_ip}:8000")


def get_gateway_authentication(
    user_id: UserID, password: SecretStr
) -> SimpleAuthentication:
    return SimpleAuthentication(username=f"{user_id}", password=password)
