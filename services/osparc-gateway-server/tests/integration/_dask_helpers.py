from typing import NamedTuple

from dask_gateway_server.app import DaskGateway


class DaskGatewayServer(NamedTuple):
    address: str
    proxy_address: str
    password: str
    server: DaskGateway
