from datetime import timedelta
from typing import Annotated

from pydantic import Field
from pydantic_settings import SettingsConfigDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings

from .base import BaseCustomSettings


class CelerySettings(BaseCustomSettings):
    CELERY_BROKER: Annotated[
        RabbitSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    CELERY_RESULT_BACKEND: Annotated[
        RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]
    CELERY_RESULT_EXPIRES: Annotated[
        timedelta,
        Field(
            description="Time (in seconds, or a timedelta object) for when after stored task tombstones will be deleted."
        ),
    ] = timedelta(days=7)
    CELERY_RESULT_PERSISTENT: Annotated[
        bool,
        Field(
            description="If set to True, result messages will be persistent (after a broker restart)."
        ),
    ] = False

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "CELERY_BROKER": {
                        "RABBIT_USER": "guest",
                        "RABBIT_SECURE": False,
                        "RABBIT_PASSWORD": "guest",
                        "RABBIT_HOST": "localhost",
                        "RABBIT_PORT": 5672,
                    },
                    "CELERY_RESULT_BACKEND": {
                        "REDIS_HOST": "localhost",
                        "REDIS_PORT": 6379,
                    },
                    "CELERY_RESULT_EXPIRES": timedelta(days=1),
                    "CELERY_RESULT_PERSISTENT": True,
                }
            ],
        }
    )
