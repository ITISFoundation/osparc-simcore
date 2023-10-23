import os

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    portainer_url: str
    portainer_username: str
    portainer_password: str
    starts_with: str
    swarm_stack_name: str
    portainer_endpoint_version: int


def get_settings(env_file, deployment):
    # pylint: disable=too-many-return-statements
    load_dotenv(env_file)

    if deployment == "master":
        portainer_url = os.getenv("MASTER_PORTAINER_URL")
        portainer_username = os.getenv("MASTER_PORTAINER_USERNAME")
        portainer_password = os.getenv("MASTER_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="master-simcore_master",
            swarm_stack_name="master-simcore",
            portainer_endpoint_version=1,
        )
    if deployment == "dalco-staging":
        portainer_url = os.getenv("DALCO_STAGING_PORTAINER_URL")
        portainer_username = os.getenv("DALCO_STAGING_PORTAINER_USERNAME")
        portainer_password = os.getenv("DALCO_STAGING_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="staging-simcore_staging",
            swarm_stack_name="staging-simcore",
            portainer_endpoint_version=1,
        )
    if deployment == "dalco-production":
        portainer_url = os.getenv("DALCO_PRODUCTION_PORTAINER_URL")
        portainer_username = os.getenv("DALCO_PRODUCTION_PORTAINER_USERNAME")
        portainer_password = os.getenv("DALCO_PRODUCTION_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="production-simcore_production",
            swarm_stack_name="production-simcore",
            portainer_endpoint_version=1,
        )
    if deployment == "tip-production":
        portainer_url = os.getenv("TIP_PRODUCTION_PORTAINER_URL")
        portainer_username = os.getenv("TIP_PRODUCTION_PORTAINER_USERNAME")
        portainer_password = os.getenv("TIP_PRODUCTION_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="production-simcore_production",
            swarm_stack_name="production-simcore",
            portainer_endpoint_version=2,
        )
    if deployment == "aws-staging":
        portainer_url = os.getenv("AWS_STAGING_PORTAINER_URL")
        portainer_username = os.getenv("AWS_STAGING_PORTAINER_USERNAME")
        portainer_password = os.getenv("AWS_STAGING_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="staging-simcore_staging",
            swarm_stack_name="staging-simcore",
            portainer_endpoint_version=2,
        )
    if deployment == "aws-production":
        portainer_url = os.getenv("AWS_PRODUCTION_PORTAINER_URL")
        portainer_username = os.getenv("AWS_PRODUCTION_PORTAINER_USERNAME")
        portainer_password = os.getenv("AWS_PRODUCTION_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="production-simcore_production",
            swarm_stack_name="production-simcore",
            portainer_endpoint_version=2,
        )
    else:
        raise ValueError("Invalid environment type provided.")
