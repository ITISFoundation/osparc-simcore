from typing import Optional


class DatcoreAdapterException(Exception):
    """basic exception for errors raised in datcore-adapter"""

    def __init__(self, msg: Optional[str] = None) -> None:
        super().__init__(
            msg or "Unexpected error occured in datcore-adapter subpackage"
        )


class DatcoreAdapterClientError(DatcoreAdapterException):
    """client error when accessing server"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg)


class DatcoreAdapterTimeoutError(DatcoreAdapterException):
    """client timeout when accessing datcore adapter server"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg)


class DatcoreAdapterServerError(DatcoreAdapterException):
    """server error"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg or "Unexpected error in datcore-adapter server")
