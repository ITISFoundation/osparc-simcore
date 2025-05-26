from aws_library.ec2 import EC2InstanceData
from fastapi import FastAPI
from models_library.clusters import ClusterAuthentication
from pydantic import AnyUrl, TypeAdapter

from ..core.settings import get_application_settings


def get_scheduler_url(ec2_instance: EC2InstanceData) -> AnyUrl:
    return TypeAdapter(AnyUrl).validate_python(
        f"tls://{ec2_instance.aws_private_dns}:8786"
    )


def get_scheduler_auth(app: FastAPI) -> ClusterAuthentication:
    return get_application_settings(
        app
    ).CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_AUTH
