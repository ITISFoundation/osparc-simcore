import os
from pathlib import Path
from typing import Final, Self

from dotenv import load_dotenv
from pydantic import BaseModel, Field, HttpUrl, SecretStr, TypeAdapter, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import Deployment

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
_LEGACY_DEPLOYMENT_CONFIG: dict[str, tuple[str, str, int]] = {
    "aws-nih-production": ("AWS_NIH_PRODUCTION", "production-simcore_production", 2),
    "aws-staging": ("AWS_STAGING", "staging-simcore_staging", 2),
    "aws-zmt-production": ("AWS_ZMT_PRODUCTION", "staging-simcore_staging", 1),
    "dalco-production": ("DALCO_PRODUCTION", "production-simcore_production", 1),
    "dalco-staging": ("DALCO_STAGING", "staging-simcore_staging", 1),
    "master": ("MASTER", "master-simcore_master", 1),
    "tip-production": ("TIP_PRODUCTION", "production-simcore_production", 2),
}

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
    portainer_password: SecretStr = Field(..., validation_alias="PORTAINER_PASSWORD")
    swarm_stack_name: str = Field(..., validation_alias="SWARM_STACK_NAME")
    portainer_endpoint_version: int
    starts_with: str
    portainer_url: HttpUrl | None = None

    model_config = SettingsConfigDict(extra="ignore")

    @model_validator(mode="after")
    def deduce_portainer_url(self) -> Self:
        self.portainer_url = TypeAdapter(HttpUrl).validate_python(f"https://{self.PORTAINER_DOMAIN}")
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
            msg = f"Unknown {deployment=}. Please setupa a new ReleaseSettings for this configuration"
            raise ValueError(msg)

    return settings


class LegacySettings(BaseModel):
    portainer_url: str
    portainer_username: str
    portainer_password: SecretStr
    starts_with: str
    swarm_stack_name: str
    portainer_endpoint_version: int


def get_legacy_settings(env_file, deployment: str) -> LegacySettings:
    load_dotenv(env_file)

    deployment_config = _LEGACY_DEPLOYMENT_CONFIG.get(deployment)
    if deployment_config is None:
        msg = "Invalid environment type provided."
        raise ValueError(msg)

    env_prefix, starts_with, portainer_endpoint_version = deployment_config
    portainer_url = os.getenv(f"{env_prefix}_PORTAINER_URL")
    portainer_username = os.getenv(f"{env_prefix}_PORTAINER_USERNAME")
    portainer_password = os.getenv(f"{env_prefix}_PORTAINER_PASSWORD")

    return LegacySettings(
        portainer_url=portainer_url,
        portainer_username=portainer_username,
        portainer_password=portainer_password,
        starts_with=starts_with,
        swarm_stack_name=starts_with.split("_")[0],
        portainer_endpoint_version=portainer_endpoint_version,
    )
