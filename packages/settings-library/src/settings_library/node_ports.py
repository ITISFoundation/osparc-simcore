import json
from typing import Any, Final

from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr
from pydantic.json import pydantic_encoder

from ._constants import MINUTE
from .base import BaseCustomSettings
from .postgres import PostgresSettings
from .storage import StorageSettings

NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE: Final[NonNegativeInt] = 3


class StorageAuthSettings(StorageSettings):
    STORAGE_LOGIN: str
    STORAGE_PASSWORD: SecretStr

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
    NODE_PORTS_STORAGE: StorageSettings = Field(auto_default_from_env=True)
    NODE_PORTS_STORAGE_AUTH: StorageAuthSettings | None = Field(
        auto_default_from_env=True
    )

    POSTGRES_SETTINGS: PostgresSettings = Field(auto_default_from_env=True)

    NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S: NonNegativeInt = 5 * MINUTE
    NODE_PORTS_IO_NUM_RETRY_ATTEMPTS: PositiveInt = 5
    NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS: NonNegativeInt = (
        NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE
    )
