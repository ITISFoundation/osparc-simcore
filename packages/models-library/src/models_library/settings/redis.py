from typing import Optional

from pydantic import BaseSettings, PositiveInt, validator
from pydantic.networks import RedisDsn
from pydantic.types import SecretStr


class RedisConfig(BaseSettings):
    # host
    host: str = "redis"
    port: PositiveInt = 6789

    # auth
    user: Optional[str] = None
    password: Optional[SecretStr] = None

    # db
    db: Optional[str] = "0"

    dsn: Optional[RedisDsn] = None

    @validator("dsn", pre=True)
    @classmethod
    def autofill_dsn(cls, v, values):
        if not v and all(key in values for key in cls.__fields__ if key != "dsn"):
            return RedisDsn.build(
                scheme="redis",
                user=values["user"] or None,
                password=values["password"].get_secret_value()
                if values["password"]
                else None,
                host=values["host"],
                port=f"{values['port']}",
                path=f"/{values['db']}",
            )
        return v

    class Config:
        env_prefix = "REDIS_"
