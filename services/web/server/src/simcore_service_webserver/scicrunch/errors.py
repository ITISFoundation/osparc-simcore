import logging

from aiohttp import web_exceptions
from servicelib.aiohttp import status

from ..errors import WebServerBaseError

_logger = logging.getLogger(__name__)


class ScicrunchError(WebServerBaseError):
    msg_template = "{reason}"


class ScicrunchServiceError(ScicrunchError):
    """Typically raised when
    - service down
    - requests time-out
    - not reachable (e.g. network slow)
    """


class ScicrunchAPIError(ScicrunchError):
    """Typically raised when
    - service API changed
    - ValidatinError in response
    - Different entrypoint
    """


class ScicrunchConfigError(ScicrunchError):
    """Typicall raised when
    - Invalid token
    - submodule disabled
    """


class InvalidRRIDError(ScicrunchError):
    msg_template = "Invalid RRID {rrid}"


def map_to_scicrunch_error(rrid: str, error_code: int, message: str) -> ScicrunchError:
    # NOTE: error handling designed based on test_scicrunch_service_api.py
    assert (
        status.HTTP_400_BAD_REQUEST
        <= error_code
        <= status.HTTP_511_NETWORK_AUTHENTICATION_REQUIRED
    ), error_code  # nosec

    custom_error = ScicrunchError(reason="Unexpected error in scicrunch.org")

    if error_code == web_exceptions.HTTPBadRequest.status_code:
        custom_error = InvalidRRIDError(rrid=rrid)

    elif error_code == web_exceptions.HTTPNotFound.status_code:
        custom_error = InvalidRRIDError(msg_template=f"Did not find any '{rrid}'")

    elif error_code == web_exceptions.HTTPUnauthorized.status_code:
        custom_error = ScicrunchConfigError(
            reason="osparc was not authorized to access scicrunch.org."
            "Please check API access tokens."
        )

    elif (
        error_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
    ):  # scicrunch.org server error
        custom_error = ScicrunchServiceError(
            reason="scicrunch.org cannot perform our requests"
        )

    return custom_error
