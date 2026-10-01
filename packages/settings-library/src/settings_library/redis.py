from enum import IntEnum

from pydantic.networks import RedisDsn
from pydantic.types import SecretStr
from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings
from .basic_types import PortInt


class RedisDatabase(IntEnum):
    RESOURCES = 0
    LOCKS = 1
    VALIDATION_CODES = 2
    SCHEDULED_MAINTENANCE = 3
    USER_NOTIFICATIONS = 4
    ANNOUNCEMENTS = 5
    LONG_RUNNING_TASKS = 6
    DEFERRED_TASKS = 7
    DYNAMIC_SERVICES = 8
    CELERY_TASKS = 9
    DOCUMENTS = 10
    AIOCACHE = 11


class RedisSettings(BaseCustomSettings):
    # host
    REDIS_SECURE: bool = False
    REDIS_HOST: str = "redis"
    REDIS_PORT: PortInt = 6789

    # auth
    REDIS_USER: str | None = None
    REDIS_PASSWORD: SecretStr | None = None

    # NOTE: shifts every `RedisDatabase` index by this amount (default 0 = no change, i.e. the
    # exact same DSNs as before this field existed). Lets multiple otherwise-independent app
    # instances share ONE physical redis/valkey server without colliding on the same logical
    # databases (e.g. pytest-xdist workers each reserving their own bank of database indices).
    REDIS_DB_OFFSET: int = 0

    def build_redis_dsn(self, db_index: RedisDatabase) -> str:
        return str(
            RedisDsn.build(  # pylint: disable=no-member
                scheme="rediss" if self.REDIS_SECURE else "redis",
                username=self.REDIS_USER or None,
                password=(self.REDIS_PASSWORD.get_secret_value() if self.REDIS_PASSWORD else None),
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                path=f"{db_index + self.REDIS_DB_OFFSET}",
            )
        )

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                # minimal required
                {
                    "REDIS_USER": "user",
                    "REDIS_PASSWORD": "foobar",  # NOSONAR
                }
            ],
        }
    )
