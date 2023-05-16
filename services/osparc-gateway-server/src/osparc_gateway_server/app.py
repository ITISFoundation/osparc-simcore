import sys

from dask_gateway_server.app import main


def start() -> None:
    sys.exit(main())
