from pydantic import Field, NonNegativeInt, PositiveInt
from settings_library.base import BaseCustomSettings
from settings_library.postgres import PostgresSettings
from settings_library.storage import StorageSettings

from .constants import MINUTE


class NodePortsSettings(BaseCustomSettings):
    NODE_PORTS_STORAGE: StorageSettings = Field(auto_default_from_env=True)
    POSTGRES_SETTINGS: PostgresSettings = Field(auto_default_from_env=True)

    NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S: NonNegativeInt = 5 * MINUTE
    NODE_PORTS_IO_NUM_RETRY_ATTEMPTS: PositiveInt = 5
    NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS: PositiveInt = 3
