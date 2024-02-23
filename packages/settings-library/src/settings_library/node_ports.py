import json
from datetime import timedelta
from typing import Any, Final

from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr, root_validator
from pydantic.json import pydantic_encoder

from .base import BaseCustomSettings
from .postgres import PostgresSettings
from .storage import StorageSettings

NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE: Final[NonNegativeInt] = 3


class StorageAuthSettings(StorageSettings):
    STORAGE_USERNAME: str | None
    STORAGE_PASSWORD: SecretStr | None

    @property
    def were_credentials_provided(self) -> bool:
        return self.STORAGE_USERNAME is not None and self.STORAGE_PASSWORD is not None

    @classmethod
    @root_validator
    def both_fields_set_or_unset(cls, values):
        username = values["STORAGE_USERNAME"]
        password = values["STORAGE_PASSWORD"]
        if (username is None) != (password is None):
            msg = f"Both {username=} and {password=} must be either set or unset!"
            raise ValueError(msg)
        return values

    def unsafe_dict(self):
        data: dict[str, Any] = self.dict()
        data["STORAGE_PASSWORD"] = (
            self.STORAGE_PASSWORD.get_secret_value() if self.STORAGE_PASSWORD else None
        )
        return data

    def unsafe_json(self):
        d = self.unsafe_dict()
        return json.dumps(d, default=pydantic_encoder)


class NodePortsSettings(BaseCustomSettings):
    NODE_PORTS_STORAGE_AUTH: StorageAuthSettings = Field(auto_default_from_env=True)

    POSTGRES_SETTINGS: PostgresSettings = Field(auto_default_from_env=True)

    NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S: NonNegativeInt = int(
        timedelta(minutes=5).total_seconds()
    )
    NODE_PORTS_IO_NUM_RETRY_ATTEMPTS: PositiveInt = 5
    NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS: NonNegativeInt = (
        NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE
    )
