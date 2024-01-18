import os

from dotenv import load_dotenv
from pydantic import BaseModel, BaseSettings, Field

DEPLOYMENTS = [
    "master",
    "dalco-staging",
    "dalco-production",
    "tip-production",
    "aws-zmt-production",
    "aws-nih-production",
    "aws-staging",
]


class NewSettings(BaseSettings):
    OSPARC_DEPLOYMENT_TARGET: str
    portainer_url: str = Field(..., env="PORTAINER_DOMAIN")
    portainer_username: str = Field(..., env="PORTAINER_USER")
    portainer_password: str = Field(..., env="PORTAINER_PASSWORD")
    swarm_stack_name: str = Field(..., env="SWARM_STACK_NAME")
    portainer_endpoint_version: int

    @property
    def starts_with(self) -> str:
        return {
            "master": "master-simcore_master",
            "dalco-staging": "staging-simcore_staging",
            "dalco-production": "production-simcore_production",
            "tip-production": "production-simcore_production",
            "aws-staging": "staging-simcore_staging",
            "aws-nih-production": "production-simcore_production",
            "aws-zmt-production": "staging-simcore_staging",
        }[self.OSPARC_DEPLOYMENT_TARGET]


def get_new_settings(env_file_path, deployment: str):

    match deployment:
        case "master":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="MASTER_",
                portainer_endpoint_version=1,
            )
        case "dalco-staging":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="DALCO_STAGING_",
                portainer_endpoint_version=1,
            )
        case "dalco-production":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="TIP_PRODUCTION_",
                portainer_endpoint_version=1,
            )
        case "tip-production":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="MASTER",
                portainer_endpoint_version=2,
            )
        case "aws-staging":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="MASTER",
                portainer_endpoint_version=2,
            )
        case "aws-nih-production":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="MASTER",
                portainer_endpoint_version=2,
            )
        case "aws-zmt-production":
            settings = NewSettings(
                _enf_file=env_file_path,
                _env_prefix="MASTER",
                portainer_endpoint_version=1,
            )
        case _:
            msg = f"Invalid {deployment=}"
            raise ValueError(msg)

    return settings


class Settings(BaseModel):
    portainer_url: str
    portainer_username: str
    portainer_password: str
    starts_with: str
    swarm_stack_name: str
    portainer_endpoint_version: int


def get_settings(env_file, deployment: str) -> Settings:
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
    if deployment == "aws-nih-production":
        portainer_url = os.getenv("AWS_NIH_PRODUCTION_PORTAINER_URL")
        portainer_username = os.getenv("AWS_NIH_PRODUCTION_PORTAINER_USERNAME")
        portainer_password = os.getenv("AWS_NIH_PRODUCTION_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="production-simcore_production",
            swarm_stack_name="production-simcore",
            portainer_endpoint_version=2,
        )
    if deployment == "aws-zmt-production":
        portainer_url = os.getenv("AWS_ZMT_PRODUCTION_PORTAINER_URL")
        portainer_username = os.getenv("AWS_ZMT_PRODUCTION_PORTAINER_USERNAME")
        portainer_password = os.getenv("AWS_ZMT_PRODUCTION_PORTAINER_PASSWORD")

        return Settings(
            portainer_url=portainer_url,
            portainer_username=portainer_username,
            portainer_password=portainer_password,
            starts_with="staging-simcore_staging",
            swarm_stack_name="staging-simcore",
            portainer_endpoint_version=1,
        )
    else:
        msg = "Invalid environment type provided."
        raise ValueError(msg)
