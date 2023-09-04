class DatcoreAdapterError(Exception):
    """basic exception for errors raised in datcore-adapter"""

    def __init__(self, msg: str | None = None) -> None:
        super().__init__(
            msg or "Unexpected error occured in datcore-adapter subpackage"
        )


class DatcoreAdapterClientError(DatcoreAdapterError):
    """client error when accessing server"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg)


class DatcoreAdapterTimeoutError(DatcoreAdapterError):
    """client timeout when accessing datcore adapter server"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg)


class DatcoreAdapterServerError(DatcoreAdapterError):
    """server error"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg or "Unexpected error in datcore-adapter server")
