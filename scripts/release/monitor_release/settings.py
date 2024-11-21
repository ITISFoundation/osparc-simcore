import os
from pathlib import Path
from typing import Final, Self

from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import Deployment

#
_DEPLOYMENTS_MAP = {
    Deployment.master: "osparc-master.speag.com",
    Deployment.aws_staging: "osparc-staging.io",
    Deployment.dalco_staging: "osparc-staging.speag.com",
    Deployment.aws_nih_production: "osparc.io",
    Deployment.dalco_production: "osparc.speag.com",
    Deployment.tip_production: "tip.itis.swiss",
    Deployment.aws_zmt_production: "sim4life.io",
}
_DEPLOYMENTS_IMAP = {v: k for k, v in _DEPLOYMENTS_MAP.items()}

SECRETS_CONFIG_FILE_NAME: Final[str] = "repo.config"


def get_repo_configs_paths(top_folder: Path) -> list[Path]:
    return list(top_folder.rglob(SECRETS_CONFIG_FILE_NAME))


def get_deployment_name_or_none(repo_config: Path) -> str | None:
    if repo_config.name == "repo.config":
        return repo_config.resolve().parent.name
    return None


class ReleaseSettings(BaseSettings):
    OSPARC_DEPLOYMENT_TARGET: str
    PORTAINER_DOMAIN: str

    portainer_username: str = Field(..., validation_alias="PORTAINER_USER")
    portainer_password: str = Field(..., validation_alias="PORTAINER_PASSWORD")
    swarm_stack_name: str = Field(..., validation_alias="SWARM_STACK_NAME")
    portainer_endpoint_version: int
    starts_with: str
    portainer_url: HttpUrl | None = None

    model_config = SettingsConfigDict(extra="ignore")

    @model_validator(mode="after")
    def deduce_portainer_url(self) -> Self:
        self.portainer_url = TypeAdapter(HttpUrl).validate_python(
            f"https://{self.PORTAINER_DOMAIN}"
        )
        return self


def get_release_settings(env_file_path: Path):

    # NOTE: these conversions and checks are done to keep
    deployment_name = get_deployment_name_or_none(env_file_path)
    if deployment_name is None:
        msg = f"{env_file_path=} cannot be matched to any deployment"
        raise ValueError(msg)

    deployment = _DEPLOYMENTS_IMAP.get(deployment_name)
    if deployment is None:
        msg = f"{deployment_name=} cannot be matched to any known deployment {set(_DEPLOYMENTS_IMAP.keys())}"
        raise ValueError(msg)

    match deployment_name:
        # NOTE: `portainer_endpoint_version` and `starts_with` cannot be deduced from the
        # information in the `repo.config`. For that reason we have to set
        # those values in the code.
        #

        case "osparc-master.speag.com":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=1,
                starts_with="master-simcore_master",
            )
        case "osparc-staging.speag.com":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=1,
                starts_with="staging-simcore_staging",
            )
        case "osparc.speag.com":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=1,
                starts_with="production-simcore_production",
            )
        case "tip.itis.swiss":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=2,
                starts_with="production-simcore_production",
            )
        case "osparc-staging.io":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=2,
                starts_with="staging-simcore_staging",
            )
        case "osparc.io":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=2,
                starts_with="production-simcore_production",
            )
        case "sim4life.io":
            settings = ReleaseSettings(
                _env_file=env_file_path,  # type: ignore
                portainer_endpoint_version=1,
                starts_with="staging-simcore_staging",
            )
        case _:
            msg = f"Unkown {deployment=}. Please setupa a new ReleaseSettings for this configuration"
            raise ValueError(msg)

    return settings


class LegacySettings(BaseModel):
    portainer_url: str
    portainer_username: str
    portainer_password: str
    starts_with: str
    swarm_stack_name: str
    portainer_endpoint_version: int


def get_legacy_settings(env_file, deployment: str) -> LegacySettings:
    # pylint: disable=too-many-return-statements
    load_dotenv(env_file)

    if deployment == "master":
        portainer_url = os.getenv("MASTER_PORTAINER_URL")
        portainer_username = os.getenv("MASTER_PORTAINER_USERNAME")
        portainer_password = os.getenv("MASTER_PORTAINER_PASSWORD")

        return LegacySettings(
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

        return LegacySettings(
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

        return LegacySettings(
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

        return LegacySettings(
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

        return LegacySettings(
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

        return LegacySettings(
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

        return LegacySettings(
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
