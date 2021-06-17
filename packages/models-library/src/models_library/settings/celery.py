from pydantic import BaseSettings, PositiveInt

from .rabbit import RabbitConfig
from .redis import RedisConfig


class CeleryConfig(BaseSettings):
    @classmethod
    def create_from_env(cls, **override) -> "CeleryConfig":
        # this calls trigger env parsers
        return cls(rabbit=RabbitConfig(), redis=RedisConfig(db="2"), **override)

    # NOTE: Defaults are evaluated at import time, use create_from_env to build instances
    rabbit: RabbitConfig = RabbitConfig()
    redis: RedisConfig = RedisConfig()

    task_name: str = "simcore.comp.task"

    publication_timeout: PositiveInt = 60

    @property
    def broker_url(self):
        return self.rabbit.dsn

    @property
    def result_backend(self):
        return self.redis.dsn
