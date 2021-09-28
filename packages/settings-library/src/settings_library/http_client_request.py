from typing import Optional

from pydantic import Field

from .base import BaseCustomSettings


class ClientRequestSettings(BaseCustomSettings):
    # NOTE: when updating the defaults please make sure to search for the env vars
    # in all the project, they also need to be updated inside the service-library
    HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT: Optional[int] = Field(
        default=20,
        description="timeout used for outgoing http requests",
    )

    HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT: Optional[int] = Field(
        default=None,
        description=(
            "Maximal number of seconds for acquiring a connection"
            " from pool. The time consists connection establishment"
            " for a new connection or waiting for a free connection"
            " from a pool if pool connection limits are exceeded. "
            "For pure socket connection establishment time use sock_connect."
        ),
    )

    HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT: Optional[int] = Field(
        default=5,
        description=(
            "aiohttp specific field used in ClientTimeout, timeout for connecting to a "
            "peer for a new connection not given a pool"
        ),
    )
