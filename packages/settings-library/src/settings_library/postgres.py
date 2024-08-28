from typing import Self
import urllib.parse
from functools import cached_property

from pydantic import (
    AliasChoices,
    ConfigDict,
    Field,
    PostgresDsn,
    SecretStr,
    model_validator,
)

from .base import BaseCustomSettings
from .basic_types import PortInt


class PostgresSettings(BaseCustomSettings):
    # entrypoint
    POSTGRES_HOST: str
    POSTGRES_PORT: PortInt = PortInt(5432)

    # auth
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr

    # database
    POSTGRES_DB: str = Field(..., description="Database name")

    # pool connection limits
    POSTGRES_MINSIZE: int = Field(
        default=1, description="Minimum number of connections in the pool", ge=1
    )
    POSTGRES_MAXSIZE: int = Field(
        default=50, description="Maximum number of connections in the pool", ge=1
    )

    POSTGRES_CLIENT_NAME: str | None = Field(
        default=None,
        description="Name of the application connecting the postgres database, will default to use the host hostname (hostname on linux)",
        validation_alias=AliasChoices(
            "POSTGRES_CLIENT_NAME",
            # This is useful when running inside a docker container, then the hostname is set each client gets a different name
            "HOST",
            "HOSTNAME",
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                # minimal required
                {
                    "POSTGRES_HOST": "localhost",
                    "POSTGRES_PORT": "5432",
                    "POSTGRES_USER": "usr",
                    "POSTGRES_PASSWORD": "secret",
                    "POSTGRES_DB": "db",
                }
            ],
        }
    )

    @model_validator(mode='after')
    def _check_size(self) -> Self:
        if not (self.POSTGRES_MINSIZE <= self.POSTGRES_MAXSIZE):
            msg = f"assert POSTGRES_MINSIZE={self.POSTGRES_MINSIZE} <= POSTGRES_MAXSIZE={self.POSTGRES_MAXSIZE}"
            raise ValueError(msg)
        return self

    @cached_property
    def dsn(self) -> str:
        dsn: str = PostgresDsn.build(
            scheme="postgresql",
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=f"{self.POSTGRES_PORT}",
            path=f"/{self.POSTGRES_DB}",
        )
        return dsn

    @cached_property
    def dsn_with_async_sqlalchemy(self) -> str:
        dsn: str = PostgresDsn.build(
            scheme="postgresql+asyncpg",
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=f"{self.POSTGRES_PORT}",
            path=f"/{self.POSTGRES_DB}",
        )
        return dsn

    @cached_property
    def dsn_with_query(self) -> str:
        """Some clients do not support queries in the dsn"""
        dsn = self.dsn
        if self.POSTGRES_CLIENT_NAME:
            dsn += "?" + urllib.parse.urlencode(
                {"application_name": self.POSTGRES_CLIENT_NAME}
            )
        return dsn
