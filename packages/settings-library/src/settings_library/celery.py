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
    CELERY_RESULTS_BACKEND: Annotated[
        RedisSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [],
        }
    )
