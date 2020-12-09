from typing import Optional

from pydantic import BaseSettings, Field


class ClientRequestSettings(BaseSettings):
    # NOTE: when updating the defaults please make sure to search for the env vars
    # in all the project, they also need to be updated inside the service-library
    total_timeout: Optional[int] = Field(
        default=20,
        description="timeout used for outgoing http requests",
        env="HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT",
    )

    aiohttp_connect_timeout: Optional[int] = Field(
        default=5,
        description=(
            "aiohttp specific field used in ClientTimeout, timeout for connecting to a "
            "peer for a new connection waiting for a free connection from a pool if "
            "pool connection limits are exceeded"
        ),
        env="HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT",
    )

    aiohttp_sock_connect_timeout: Optional[int] = Field(
        default=5,
        description=(
            "aiohttp specific field used in ClientTimeout, timeout for connecting to a "
            "peer for a new connection not given a pool"
        ),
        env="HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT",
    )

client_request_settings = ClientRequestSettings()