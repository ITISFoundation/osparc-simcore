from typing import Optional

from pydantic import BaseSettings, Field


class ClientRequestSettings(BaseSettings):
    total_timeout: Optional[int] = Field(
        default=20,
        description="timeout used for outgoing http requests",
        env="HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT",
    )
