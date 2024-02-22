from typing import ClassVar, Final

from models_library.basic_types import PortInt
from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr

from ._constants import MINUTE
from .base import BaseCustomSettings
from .postgres import PostgresSettings
from .storage import StorageSettings

NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE: Final[NonNegativeInt] = 3


class StorageAuthSettings(BaseCustomSettings):
    NODE_PORTS_STORAGE_HOST: str
    NODE_PORTS_STORAGE_PORT: PortInt

    NODE_PORTS_STORAGE_LOGIN: str
    NODE_PORTS_STORAGE_PASSWORD: SecretStr

    class Config:
        json_encoders: ClassVar = {
            SecretStr: lambda v: v.get_secret_value() if v else None,
        }


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
