import urllib.parse
from functools import cached_property
from typing import Optional

from pydantic import Field, PostgresDsn, SecretStr, conint, validator

from .base import BaseCustomSettings
from .basic_types import PortInt

IntGE1 = conint(ge=1)


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
    POSTGRES_MINSIZE: IntGE1 = Field(
        1, description="Minimum number of connections in the pool"
    )
    POSTGRES_MAXSIZE: IntGE1 = Field(
        50, description="Maximum number of connections in the pool"
    )

    POSTGRES_CLIENT_NAME: Optional[str] = Field(
        None,
        description="Name of the application connecting the postgres database, will default to use the host hostname (hostname on linux)",
        env=["HOST", "HOSTNAME", "POSTGRES_CLIENT_NAME"],
    )

    @validator("POSTGRES_MAXSIZE")
    @classmethod
    def _check_size(cls, v, values):
        if not (values["POSTGRES_MINSIZE"] <= v):
            raise ValueError(
                f"assert POSTGRES_MINSIZE={values['POSTGRES_MINSIZE']} <= POSTGRES_MAXSIZE={v}"
            )
        return v

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
    def dsn_with_query(self) -> str:
        """Some clients do not support queries in the dsn"""
        dsn = self.dsn
        if self.POSTGRES_CLIENT_NAME:
            dsn += "?" + urllib.parse.urlencode(
                {"application_name": self.POSTGRES_CLIENT_NAME}
            )
        return dsn
