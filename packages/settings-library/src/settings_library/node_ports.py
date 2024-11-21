from datetime import timedelta
from typing import Annotated, Final, Self

from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr, model_validator

from .base import BaseCustomSettings
from .postgres import PostgresSettings
from .storage import StorageSettings

NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE: Final[NonNegativeInt] = 3


class StorageAuthSettings(StorageSettings):
    STORAGE_USERNAME: str | None = None
    STORAGE_PASSWORD: SecretStr | None = None
    STORAGE_SECURE: bool = False

    @property
    def auth_required(self) -> bool:
        # NOTE: authentication is required to an issue with docker networks
        # for details see https://github.com/ITISFoundation/osparc-issues/issues/1264
        return self.STORAGE_USERNAME is not None and self.STORAGE_PASSWORD is not None

    @model_validator(mode="after")
    def _validate_auth_fields(self) -> Self:
        username = self.STORAGE_USERNAME
        password = self.STORAGE_PASSWORD
        if (username is None) != (password is None):
            msg = f"Both {username=} and {password=} must be either set or unset!"
            raise ValueError(msg)
        return self


class NodePortsSettings(BaseCustomSettings):
    NODE_PORTS_STORAGE_AUTH: Annotated[
        StorageAuthSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    POSTGRES_SETTINGS: Annotated[
        PostgresSettings, Field(json_schema_extra={"auto_default_from_env": True})
    ]

    NODE_PORTS_MULTIPART_UPLOAD_COMPLETION_TIMEOUT_S: NonNegativeInt = int(
        timedelta(minutes=5).total_seconds()
    )
    NODE_PORTS_IO_NUM_RETRY_ATTEMPTS: PositiveInt = 5
    NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS: NonNegativeInt = (
        NODE_PORTS_400_REQUEST_TIMEOUT_ATTEMPTS_DEFAULT_VALUE
    )
