from enum import Enum
from functools import cached_property
from typing import Optional

from pydantic import Field
from pydantic.networks import RedisDsn
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class RedisDatabase(int, Enum):
    RESOURCES = 0
    LOCKS = 1
    VALIDATION_CODES = 2
    SCHEDULED_MAINTENANCE = 3
    USER_NOTIFICATIONS = 4


class RedisSettings(BaseCustomSettings):
    # host
    REDIS_HOST: str = "redis"
    REDIS_PORT: PortInt = 6789

    # auth
    REDIS_USER: Optional[str] = None
    REDIS_PASSWORD: Optional[SecretStr] = None

    # NOTE: i would like to remove these since the enum should suffice
    # redis databases (db)
    REDIS_RESOURCES_DB: RedisDatabase = Field(
        default=RedisDatabase.RESOURCES,
        description="typical redis DB have 16 'tables', for convenience we use this table for user resources",
    )
    REDIS_LOCKS_DB: RedisDatabase = Field(
        default=RedisDatabase.LOCKS, description="This redis table is used to put locks"
    )
    REDIS_VALIDATION_CODES_DB: RedisDatabase = Field(
        default=RedisDatabase.VALIDATION_CODES,
        description="This redis table is used to store SMS validation codes",
    )
    REDIS_SCHEDULED_MAINTENANCE_DB: RedisDatabase = Field(
        default=RedisDatabase.SCHEDULED_MAINTENANCE,
        description="This redis table is used for handling scheduled maintenance",
    )
    REDIS_USER_NOTIFICATIONS_DB: RedisDatabase = Field(
        default=RedisDatabase.USER_NOTIFICATIONS,
        description="This redis table is used for handling the notifications that have to be sent to the user",
    )

    def build_redis_dsn(self, db_index: int):
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
        return self.build_redis_dsn(self.REDIS_RESOURCES_DB)

    @cached_property
    def dsn_locks(self) -> str:
        return self.build_redis_dsn(self.REDIS_LOCKS_DB)

    @cached_property
    def dsn_validation_codes(self) -> str:
        return self.build_redis_dsn(self.REDIS_VALIDATION_CODES_DB)

    @cached_property
    def dsn_scheduled_maintenance(self) -> str:
        return self.build_redis_dsn(self.REDIS_SCHEDULED_MAINTENANCE_DB)

    @cached_property
    def dsn_user_notifications(self) -> str:
        return self.build_redis_dsn(self.REDIS_USER_NOTIFICATIONS_DB)
