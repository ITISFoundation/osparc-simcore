from typing import Final

from pydantic import Field, NonNegativeInt
from settings_library.base import BaseCustomSettings
from settings_library.r_clone import S3Provider

_MIN: Final[NonNegativeInt] = 60


class ApplicationSettings(BaseCustomSettings):
    SIMCORE_AGENT_INTERVAL_VOLUMES_CLEANUP_S: NonNegativeInt = Field(
        60 * _MIN, description="interval at which to repeat volumes cleanup"
    )

    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    S3_PROVIDER: S3Provider
    S3_REGION: str = "us-east-1"
    S3_RETRIES: int = Field(3, description="upload retries in case of error")
    S3_PARALLELISM: int = Field(5, description="parallel transfers to s3")
    EXCLUDE_FILES: list[str] = Field(
        [".hidden_do_not_remove", "key_values.json"],
        description="Files to ignore when syncing to s3",
    )
