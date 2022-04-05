from functools import cached_property
from typing import Optional

from pydantic import Field
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
    REDIS_RESOURCES_DB: int = Field(
        0,
        description="typical redis DB have 16 'tables', for convenience we use this table for user resources",
    )
    REDIS_LOCKS_DB: int = Field(1, description="This redis table is used to put locks")

    @cached_property
    def dsn_resources(self) -> str:
        return RedisDsn.build(
            scheme="redis",
            user=self.REDIS_USER or None,
            password=self.REDIS_PASSWORD.get_secret_value()
            if self.REDIS_PASSWORD
            else None,
            host=self.REDIS_HOST,
            port=f"{self.REDIS_PORT}",
            path=f"/{self.REDIS_RESOURCES_DB}",
        )

    @cached_property
    def dsn_locks(self) -> str:
        return RedisDsn.build(
            scheme="redis",
            user=self.REDIS_USER or None,
            password=self.REDIS_PASSWORD.get_secret_value()
            if self.REDIS_PASSWORD
            else None,
            host=self.REDIS_HOST,
            port=f"{self.REDIS_PORT}",
            path=f"/{self.REDIS_LOCKS_DB}",
        )
