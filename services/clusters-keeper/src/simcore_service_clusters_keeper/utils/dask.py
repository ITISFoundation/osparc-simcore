from aws_library.ec2.models import EC2InstanceData
from fastapi import FastAPI
from models_library.clusters import InternalClusterAuthentication
from pydantic import AnyUrl, parse_obj_as

from ..core.settings import get_application_settings


def get_scheduler_url(ec2_instance: EC2InstanceData) -> AnyUrl:
    url: AnyUrl = parse_obj_as(AnyUrl, f"tls://{ec2_instance.aws_private_dns}:8786")
    return url


def get_scheduler_auth(app: FastAPI) -> InternalClusterAuthentication:
    return get_application_settings(
        app
    ).CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH
