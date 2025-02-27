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


class DatcoreAdapterMultipleFilesError(DatcoreAdapterError):
    """special error to check the assumption that /packages/{package_id}/files returns only one file"""

    def __init__(self, msg: str) -> None:
        super().__init__(msg=msg)


class DatcoreAdapterResponseError(DatcoreAdapterError):
    """Basic exception for response errors"""

    def __init__(self, status: int, reason: str) -> None:
        self.status = status
        self.reason = reason
        super().__init__(
            msg=f"forwarded call failed with status {status}, reason {reason}"
        )
