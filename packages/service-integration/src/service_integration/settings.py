from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Registry(BaseModel):
    url_or_prefix: str
    user: str | None = None
    password: SecretStr | None = None


# NOTE: image names w/o a prefix default in dockerhub registry
DOCKERHUB_REGISTRY_NAME = ""


class AppSettings(BaseSettings):

    DOCKER_REGISTRIES: dict[str, Registry] = {
        "local": Registry(url_or_prefix="registry:5000")
    }
    DEFAULT_REGISTRY: str = "local"

    REGISTRY_NAME: str = Field(
        DOCKERHUB_REGISTRY_NAME,
        description="name of the registry used as prefix in images",
    )

    COMPOSE_VERSION: str = Field(
        "3.7", description="version of the docker-compose spec"
    )
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
    )

    # TODO: load from ~/.osparc/service-integration.json or env file
    # TODO: add access to secrets
    # SEE https://pydantic-docs.helpmanual.io/usage/settings/#adding-sources
