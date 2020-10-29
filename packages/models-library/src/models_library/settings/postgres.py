# pylint: disable=no-self-argument
# pylint: disable=no-self-use

from enum import Enum
from typing import Optional

from pydantic import BaseSettings, PostgresDsn, SecretStr, conint, constr, validator
from ..basic_types import PortInt, VersionTag, LogLevel

class PostgresSettings(BaseSettings):
    dns: Optional[PostgresDsn] = None

    # entrypoint
    host: str
    port: PortInt = 5432

    # auth
    user: str
    password: SecretStr

    # database
    db: str

    # pool connection limits
    minsize: int = 10
    maxsize: int = 10

    @validator("maxsize")
    def check_size(cls, v, values):
        if not (values["minsize"] <= v):
            raise ValueError(f"assert minsize={values['minsize']} <= maxsize={v}")
        return v

    @property
    def postgres_dsn(self) -> str:
        if self.dns:
            return str(self.dns)
        else:
            return PostgresDsn.build(
                scheme="postgresql",
                user=self.user,
                password=self.password.get_secret_value(),
                host=self.host,
                port=self.port,
                path=f"/{self.db}",
            )

    class Config:
        case_sensitive = False
        env_prefix = "POSTGRES_"
