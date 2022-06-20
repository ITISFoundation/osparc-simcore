from httpx import Response


class BaseClientError(Exception):
    """
    NOTE: this is derived from exception on purpose
    This module should be moved from the scope of this package
    """


class _RetryRequestError(BaseClientError):
    """used to retry request internally"""


class WrongReturnType(BaseClientError):
    def __init__(self, method, return_annotation) -> None:
        super().__init__(
            (
                f"{method=} should return an instance "
                f"of {Response}, not '{return_annotation}'!"
            )
        )


class UnexpectedStatusError(BaseClientError):
    def __init__(self, response: Response, expecting: int) -> None:
        message = (
            f"Expected status: {expecting}, got {response.status_code} for: {response.url}: "
            f"headers={response.headers}, body='{response.text}'"
        )
        super().__init__(message)
        self.response = response


class ClientTransportError(BaseClientError):
    pass


class ClientHTTPStatusError(BaseClientError):
    pass
