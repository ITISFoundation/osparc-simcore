from fastapi import FastAPI

from .core.settings import get_application_settings
from .modules.ec2 import get_ec2_client


async def create_cluster(app: FastAPI):
    ec2_client = get_ec2_client(app)
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    instances_data = await ec2_client.start_aws_instance(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        instance_type="t2.micro",
        tags={},
        startup_script="",
        number_of_instances=1,
    )
