from pydantic import Field, NonNegativeInt
from settings_library.base import BaseCustomSettings
from settings_library.postgres import PostgresSettings
from settings_library.storage import StorageSettings

from .constants import MINUTE


class NodePortsSettings(BaseCustomSettings):
    NODE_PORTS_STORAGE: StorageSettings = Field(auto_default_from_env=True)
    POSTGRES_SETTINGS: PostgresSettings = Field(auto_default_from_env=True)

    NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S: NonNegativeInt = 5 * MINUTE
    NODE_PORTS_IO_RETRY_DELAY_S: NonNegativeInt = 5 * MINUTE
