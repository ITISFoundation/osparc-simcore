from functools import cached_property

from pydantic import Field, PostgresDsn, SecretStr, conint, validator

from .base import BaseCustomSettings
from .basic_types import PortInt

IntGe1 = conint(ge=1)


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
    POSTGRES_MINSIZE: IntGe1 = Field(
        1, description="Maximum number of connections in the pool"
    )
    POSTGRES_MAXSIZE: IntGe1 = Field(
        50, description="Minimum number of connections in the pool"
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
        return PostgresDsn.build(
            scheme="postgresql",
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD.get_secret_value(),
            host=self.POSTGRES_HOST,
            port=f"{self.POSTGRES_PORT}",
            path=f"/{self.POSTGRES_DB}",
        )
