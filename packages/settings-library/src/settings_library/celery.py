from functools import cached_property

from pydantic import Field, PositiveInt
from pydantic.networks import RedisDsn

from .base import BaseCustomSettings
from .rabbit import RabbitSettings
from .redis import RedisSettings


class CelerySettings(BaseCustomSettings):

    CELERY_RABBIT: RabbitSettings = Field(
        ..., description="Rabbit is used as service broker"
    )
    CELERY_REDIS: RedisSettings = Field(
        ..., description="Redis is used as results backend"
    )

    CELERY_TASK_NAME: str = "simcore.comp.task"

    CELERY_PUBLICATION_TIMEOUT: PositiveInt = 60

    CELERY_REDIS_DB: int = 2

    @cached_property
    def broker_url(self):
        return self.CELERY_RABBIT.dsn

    @cached_property
    def result_backend(self):
        # is of type
        return RedisDsn.build(
            scheme="redis",
            user=self.CELERY_REDIS.REDIS_USER or None,
            password=self.CELERY_REDIS.REDIS_PASSWORD.get_secret_value()
            if self.CELERY_REDIS.REDIS_PASSWORD
            else None,
            host=self.CELERY_REDIS.REDIS_HOST,
            port=f"{self.CELERY_REDIS.REDIS_PORT}",
            path=f"/{self.CELERY_REDIS_DB}",
        )
