from typing import Optional

from pydantic import BaseSettings, PositiveInt
from pydantic.networks import RedisDsn
from pydantic.types import SecretStr


class RedisConfig(BaseSettings):
    dsn: Optional[RedisDsn] = None

    # host
    host: str = "redis"
    port: PositiveInt = 6789

    # auth
    user: Optional[str] = None
    password: Optional[SecretStr] = None

    # db
    db: Optional[str] = "0"

    @property
    def redis_dsn(self) -> str:
        if self.dsn:
            return str(self.dsn)
        return RedisDsn.build(
            scheme="redis",
            user=self.user or None,
            password=self.password.get_secret_value() if self.password else None,
            host=self.host,
            port=f"{self.port}",
            path=f"/{self.db}",
        )

    class Config:
        env_prefix = "REDIS_"
