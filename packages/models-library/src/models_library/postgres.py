from typing import Optional

from pydantic import BaseSettings, Extra, validator
from pydantic.networks import PostgresDsn
from pydantic.types import PositiveInt, SecretStr


class PostgresSettings(BaseSettings):
    enabled: bool = True

    # host
    host: str = "postgres"
    port: PositiveInt = 5432

    # auth
    user: str
    password: SecretStr

    # database
    db: str = "simcore"

    # pool connection limits
    minsize: int = 10
    maxsize: int = 10

    dsn: Optional[PostgresDsn] = None

    @validator("maxsize")
    @classmethod
    def check_size(cls, v, values):
        if not (values["minsize"] <= v):
            raise ValueError(f"assert minsize={values['minsize']} <= maxsize={v}")
        return v

    @validator("dsn", pre=True)
    @classmethod
    def autofill_dsn(cls, v, values):
        if v is None:
            return PostgresDsn.build(
                scheme="postgresql",
                user=values["user"],
                password=values["password"].get_secret_value(),
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['db']}",
            )
        return v

    class Config:
        case_sensitive = False
        env_file = ".env"  # SEE https://pydantic-docs.helpmanual.io/usage/settings/#dotenv-env-support
        env_prefix = "POSTGRES_"
        extra = Extra.forbid
