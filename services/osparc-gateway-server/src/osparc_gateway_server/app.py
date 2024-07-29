import sys

from dask_gateway_server.app import main  # type: ignore[import-untyped]


def start() -> None:
    sys.exit(main())
