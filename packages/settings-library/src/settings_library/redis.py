from functools import cached_property
from typing import Optional

from pydantic.networks import RedisDsn
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class RedisSettings(BaseCustomSettings):
    # host
    REDIS_HOST: str = "redis"
    REDIS_PORT: PortInt = 6789

    # auth
    REDIS_USER: Optional[str] = None
    REDIS_PASSWORD: Optional[SecretStr] = None

    # db
    REDIS_DB: Optional[str] = "0"

    @cached_property
    def dsn(self) -> str:
        return RedisDsn.build(
            scheme="redis",
            user=self.REDIS_USER or None,
            password=self.REDIS_PASSWORD.get_secret_value()
            if self.REDIS_PASSWORD
            else None,
            host=self.REDIS_HOST,
            port=f"{self.REDIS_PORT}",
            path=f"/{self.REDIS_DB}",
        )
