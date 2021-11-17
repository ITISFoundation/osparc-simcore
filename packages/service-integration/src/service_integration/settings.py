from typing import Dict, Optional

from pydantic import BaseSettings
from pydantic.main import BaseModel
from pydantic.types import SecretStr


class Registry(BaseModel):
    url_or_prefix: str
    user: Optional[str] = None
    password: Optional[SecretStr] = None


class UserSettings(BaseSettings):

    DOCKER_REGISTRIES: Dict[str, Registry] = {
        "local": Registry(url_or_prefix="registry:5000")
    }
    DEFAULT_REGISTRY: str = "local"

    class Config:
        env_file_encoding = "utf-8"

    # TODO: load from ~/.osparc/service-integration.json or env file
    # TODO: add access to secrets
    # SEE https://pydantic-docs.helpmanual.io/usage/settings/#adding-sources
