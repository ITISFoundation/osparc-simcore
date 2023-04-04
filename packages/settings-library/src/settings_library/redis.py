from enum import Enum

from pydantic.networks import RedisDsn
from pydantic.types import SecretStr

from .base import BaseCustomSettings
from .basic_types import PortInt


class RedisDatabase(int, Enum):
    # typical redis DB have 16 'tables', for convenience we use this table for user resources
    RESOURCES = 0
    # This redis table is used to put locks
    LOCKS = 1
    # This redis table is used to store SMS validation codes
    VALIDATION_CODES = 2
    # This redis table is used for handling scheduled maintenance
    SCHEDULED_MAINTENANCE = 3
    # This redis table is used for handling the notifications that have to be sent to the user
    USER_NOTIFICATIONS = 4


class RedisSettings(BaseCustomSettings):
    # host
    REDIS_HOST: str = "redis"
    REDIS_PORT: PortInt = 6789

    # auth
    REDIS_USER: str | None = None
    REDIS_PASSWORD: SecretStr | None = None

    def build_redis_dsn(self, db_index: RedisDatabase):
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
