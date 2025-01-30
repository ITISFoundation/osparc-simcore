from typing import Annotated

from pydantic import Field

from .base import BaseCustomSettings


class ClientRequestSettings(BaseCustomSettings):
    # NOTE: These entries are used in some old services as well. These need to be updated if these
    # variable names or defaults are changed.
    HTTP_CLIENT_REQUEST_TOTAL_TIMEOUT: Annotated[
        int | None,
        Field(
            description="timeout in seconds used for outgoing http requests",
        ),
    ] = 20

    HTTP_CLIENT_REQUEST_AIOHTTP_CONNECT_TIMEOUT: Annotated[
        int | None,
        Field(
            description=(
                "Maximal number of seconds for acquiring a connection"
                " from pool. The time consists connection establishment"
                " for a new connection or waiting for a free connection"
                " from a pool if pool connection limits are exceeded. "
                "For pure socket connection establishment time use sock_connect."
            ),
        ),
    ] = None

    HTTP_CLIENT_REQUEST_AIOHTTP_SOCK_CONNECT_TIMEOUT: Annotated[
        int | None,
        Field(
            description=(
                "aiohttp specific field used in ClientTimeout, timeout for connecting to a "
                "peer for a new connection not given a pool"
            ),
        ),
    ] = 5
