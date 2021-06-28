from pydantic import Field, PositiveInt

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

    @property
    def broker_url(self):
        return self.CELERY_RABBIT.dsn

    @property
    def result_backend(self):
        return self.CELERY_REDIS.dsn
