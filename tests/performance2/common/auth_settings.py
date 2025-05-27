from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class DeploymentAuth(BaseSettings):
    SC_USER_NAME: Annotated[str, Field(examples=["<your username>"])]
    SC_PASSWORD: Annotated[SecretStr, Field(examples=["<your password>"])]

    def to_auth(self) -> tuple[str, str]:
        return (self.SC_USER_NAME, self.SC_PASSWORD.get_secret_value())


class OsparcAuth(BaseSettings):
    OSPARC_USER_NAME: Annotated[str, Field(examples=["<your username>"])]
    OSPARC_PASSWORD: Annotated[SecretStr, Field(examples=["<your password>"])]
