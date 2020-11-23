from typing import Optional

from pydantic import (
    BaseSettings,
    Extra,
    Field,
    PostgresDsn,
    SecretStr,
    conint,
    validator,
)

from ..basic_types import PortInt


class PostgresSettings(BaseSettings):
    # entrypoint
    host: str
    port: PortInt = 5432

    # auth
    user: str
    password: SecretStr

    # database
    db: str

    # pool connection limits
    minsize: conint(ge=1) = 10
    maxsize: conint(ge=1) = 10

    dsn: Optional[PostgresDsn] = Field(None, description="Database Source Name")

    @validator("maxsize")
    @classmethod
    def check_size(cls, v, values):
        if not (values["minsize"] <= v):
            raise ValueError(f"assert minsize={values['minsize']} <= maxsize={v}")
        return v

    @validator("dsn", pre=True)
    @classmethod
    def autofill_dsn(cls, v, values):
        if not v and all(key in values for key in cls.__fields__ if key != "dsn"):
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
        env_prefix = "POSTGRES_"
        extra = Extra.forbid
