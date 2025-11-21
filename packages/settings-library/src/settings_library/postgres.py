from functools import cached_property
from typing import Annotated, Self
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import (
    AliasChoices,
    Field,
    NonNegativeInt,
    PostgresDsn,
    SecretStr,
    model_validator,
)
from pydantic.config import JsonDict
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
    POSTGRES_DB: Annotated[str, Field(description="Database name")]

    # pool connection limits
    POSTGRES_MINSIZE: Annotated[
        int,
        Field(
            description="Minimum number of connections in the pool that are always created and kept",
            ge=1,
        ),
    ] = 1
    POSTGRES_MAXSIZE: Annotated[
        int,
        Field(
            description="Maximum number of connections in the pool that are kept",
            ge=1,
        ),
    ] = 50
    POSTGRES_MAX_POOLSIZE: Annotated[
        int,
        Field(
            description="Maximal number of connection in asyncpg pool (without overflow), lazily created on demand"
        ),
    ] = 10
    POSTGRES_MAX_OVERFLOW: Annotated[
        NonNegativeInt, Field(description="Maximal overflow connections")
    ] = 20

    POSTGRES_CLIENT_NAME: Annotated[
        str | None,
        Field(
            description="Name of the application connecting the postgres database, will default to use the host hostname (hostname on linux)",
            validation_alias=AliasChoices(
                # This is useful when running inside a docker container, then the hostname is set each client gets a different name
                "POSTGRES_CLIENT_NAME",
                "HOST",
                "HOSTNAME",
            ),
        ),
    ] = None

    @model_validator(mode="after")
    def validate_postgres_sizes(self) -> Self:
        if self.POSTGRES_MINSIZE > self.POSTGRES_MAXSIZE:
            msg = (
                f"assert POSTGRES_MINSIZE={self.POSTGRES_MINSIZE} <= "
                f"POSTGRES_MAXSIZE={self.POSTGRES_MAXSIZE}"
            )
            raise ValueError(msg)
        return self

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

    def dsn_with_query(self, application_name: str, *, suffix: str | None) -> str:
        """Some clients do not support queries in the dsn"""
        dsn = self.dsn
        return self._update_query(dsn, application_name, suffix=suffix)

    def client_name(self, application_name: str, *, suffix: str | None) -> str:
        return f"{application_name}{'-' if self.POSTGRES_CLIENT_NAME else ''}{self.POSTGRES_CLIENT_NAME or ''}{'-' + suffix if suffix else ''}"

    def _update_query(self, uri: str, application_name: str, suffix: str | None) -> str:
        # SEE https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS
        new_params: dict[str, str] = {
            "application_name": self.client_name(application_name, suffix=suffix),
        }

        if new_params:
            parsed_uri = urlparse(uri)
            query = dict(parse_qsl(parsed_uri.query))
            query.update(new_params)
            updated_query = urlencode(query)
            return urlunparse(parsed_uri._replace(query=updated_query))
        return uri

    @staticmethod
    def _update_json_schema_extra(schema: JsonDict) -> None:
        schema.update(
            {
                "examples": [
                    # minimal required
                    {
                        "POSTGRES_HOST": "localhost",
                        "POSTGRES_PORT": "5432",
                        "POSTGRES_USER": "usr",
                        "POSTGRES_PASSWORD": "secret",
                        "POSTGRES_DB": "db",
                    },
                    # full example
                    {
                        "POSTGRES_HOST": "localhost",
                        "POSTGRES_PORT": "5432",
                        "POSTGRES_USER": "usr",
                        "POSTGRES_PASSWORD": "secret",
                        "POSTGRES_DB": "db",
                        "POSTGRES_MINSIZE": 1,
                        "POSTGRES_MAXSIZE": 50,
                        "POSTGRES_MAX_POOLSIZE": 10,
                        "POSTGRES_MAX_OVERFLOW": 20,
                        "POSTGRES_CLIENT_NAME": "my_app",  # first-choice
                        "HOST": "should be ignored",
                        "HOST_NAME": "should be ignored",
                    },
                ],
            }
        )

    model_config = SettingsConfigDict(json_schema_extra=_update_json_schema_extra)
