from pydantic_settings import SettingsConfigDict

from .base import BaseCustomSettings


class CelerySettings(BaseCustomSettings):
    model_config = SettingsConfigDict(
        json_schema_extra={
            "examples": [],
        }
    )
