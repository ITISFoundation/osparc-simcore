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

    # redis databases (db)
    REDIS_RESOURCES_DB: int = Field(
        default=0,
        description="typical redis DB have 16 'tables', for convenience we use this table for user resources",
    )
    REDIS_LOCKS_DB: int = Field(
        default=1, description="This redis table is used to put locks"
    )
    REDIS_VALIDATION_CODES_DB: int = Field(
        default=2, description="This redis table is used to store SMS validation codes"
    )
    REDIS_SCHEDULED_MAINTENANCE_DB: int = Field(
        default=3, description="This redis table is used for handling scheduled maintenance"
    )

    def _build_redis_dsn(self, db_index: int):
        return RedisDsn.build(
            scheme="redis",
            user=self.REDIS_USER or None,
            password=self.REDIS_PASSWORD.get_secret_value()
            if self.REDIS_PASSWORD
            else None,
            host=self.REDIS_HOST,
            port=f"{self.REDIS_PORT}",
            path=f"/{db_index}",
        )

    @cached_property
    def dsn_resources(self) -> str:
        return self._build_redis_dsn(self.REDIS_RESOURCES_DB)

    @cached_property
    def dsn_locks(self) -> str:
        return self._build_redis_dsn(self.REDIS_LOCKS_DB)

    @cached_property
    def dsn_validation_codes(self) -> str:
        return self._build_redis_dsn(self.REDIS_VALIDATION_CODES_DB)

    @cached_property
    def dsn_scheduled_maintenance(self) -> str:
        return self._build_redis_dsn(self.REDIS_SCHEDULED_MAINTENANCE_DB)
