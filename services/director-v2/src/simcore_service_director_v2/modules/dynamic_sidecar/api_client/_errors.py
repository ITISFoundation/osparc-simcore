"""
Exception hierarchy:

* BaseClientError
  x BaseRequestError
    + ClientHttpError
    + UnexpectedStatusError
  x WrongReturnType
"""

from httpx import Response


class BaseClientError(Exception):
    """
    Used as based for all the raised errors
    """


class WrongReturnTypeError(BaseClientError):
    """
    used internally to signal the user that the defined method
    has an invalid return time annotation
    """

    def __init__(self, method, return_annotation) -> None:
        super().__init__(
            f"{method=} should return an instance "
            f"of {Response}, not '{return_annotation}'!"
        )


class BaseClientHTTPError(BaseClientError):
    """Base class to wrap all http related client errors"""


class ClientHttpError(BaseClientHTTPError):
    """used to captures all httpx.HttpError"""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error: Exception = error


class UnexpectedStatusError(BaseClientHTTPError):
    """raised when the status of the request is not the one it was expected"""

    def __init__(self, response: Response, expecting: int) -> None:
        message = (
            f"Expected status: {expecting}, got {response.status_code} for: {response.url}: "
            f"headers={response.headers}, body='{response.text}'"
        )
        super().__init__(message)
        self.response = response
