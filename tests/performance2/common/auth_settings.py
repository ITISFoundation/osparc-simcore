from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DeploymentAuth(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    SC_USER_NAME: Annotated[str, Field(examples=["<your username>"])]
    SC_PASSWORD: Annotated[SecretStr, Field(examples=["<your password>"])]

    def to_auth(self) -> tuple[str, str]:
        return (self.SC_USER_NAME, self.SC_PASSWORD.get_secret_value())


class OsparcAuth(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    OSPARC_USER_NAME: Annotated[str | None, Field(examples=["<your username>"])] = None
    OSPARC_PASSWORD: Annotated[
        SecretStr | None, Field(examples=["<your password>"])
    ] = None
