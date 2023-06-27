from enum import Enum

from pydantic import parse_obj_as
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
    ANNOUNCEMENTS = 5


class RedisSettings(BaseCustomSettings):
    # host
    REDIS_HOST: str = "redis"
    REDIS_PORT: PortInt = parse_obj_as(PortInt, 6789)

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
