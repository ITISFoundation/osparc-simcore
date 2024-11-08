from functools import cached_property
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import (
    AliasChoices,
    Field,
    PostgresDsn,
    SecretStr,
    ValidationInfo,
    field_validator,
)
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .basic_types import PortInt


class PostgresSettings(BaseCustomSettings):
    # entrypoint
    POSTGRES_HOST: str
    POSTGRES_PORT: PortInt = 5432

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

    @field_validator("POSTGRES_MAXSIZE")
    @classmethod
    def _check_size(cls, v, info: ValidationInfo):
        if info.data["POSTGRES_MINSIZE"] > v:
            msg = f"assert POSTGRES_MINSIZE={info.data['POSTGRES_MINSIZE']} <= POSTGRES_MAXSIZE={v}"
            raise ValueError(msg)
        return v

    @cached_property
    def dsn(self) -> str:
        url = PostgresDsn.build(  # pylint: disable=no-member
            scheme="postgresql",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=f"{self.POSTGRES_DB}",
        )
        return f"{url}"

    @cached_property
    def dsn_with_async_sqlalchemy(self) -> str:
        url = PostgresDsn.build(  # pylint: disable=no-member
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            path=f"{self.POSTGRES_DB}",
        )
        return f"{url}"

    @cached_property
    def dsn_with_query(self) -> str:
        """Some clients do not support queries in the dsn"""
        dsn = self.dsn
        return self._update_query(dsn)

    def _update_query(self, uri: str) -> str:
        # SEE https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS
        new_params: dict[str, str] = {}
        if self.POSTGRES_CLIENT_NAME:
            new_params = {
                "application_name": self.POSTGRES_CLIENT_NAME,
            }

        if new_params:
            parsed_uri = urlparse(uri)
            query = dict(parse_qsl(parsed_uri.query))
            query.update(new_params)
            updated_query = urlencode(query)
            return urlunparse(parsed_uri._replace(query=updated_query))
        return uri

    model_config = SettingsConfigDict(
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
