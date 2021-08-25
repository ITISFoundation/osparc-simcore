import logging

from aiohttp import web_exceptions

logger = logging.getLogger(__name__)


class ScicrunchError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason.strip()
        super().__init__(self.reason)


class ScicrunchServiceError(ScicrunchError):
    # service down
    # requests time-out
    # not reachable (e.g. network slow)
    pass


class ScicrunchAPIError(ScicrunchError):
    # service API changed?
    # ValidationError in response
    # Different entrypoint?
    pass


class ScicrunchConfigError(ScicrunchError):
    # wrong token?
    # wrong formatting?
    pass


class InvalidRRID(ScicrunchError):
    def __init__(self, rrid_or_msg) -> None:
        super().__init__(reason=f"Invalid RRID {rrid_or_msg}")


def map_to_scicrunch_error(rrid: str, error_code: int, message: str) -> ScicrunchError:
    # NOTE: error handling designed based on test_scicrunch_service_api.py
    assert 400 <= error_code < 600, error_code  # nosec

    custom_error = ScicrunchError("Unexpected error in scicrunch.org")

    if error_code in (
        web_exceptions.HTTPBadRequest.status_code,
        web_exceptions.HTTPNotFound.status_code,
    ):
        custom_error = InvalidRRID(rrid)

    elif error_code == web_exceptions.HTTPUnauthorized.status_code:
        # might not have correct cookie?
        custom_error = ScicrunchConfigError("scicrunch.org authentication failed")

    elif error_code >= 500:  # scicrunch.org server error
        custom_error = ScicrunchServiceError(
            "scicrunch.org cannot perform our requests"
        )

    logger.error("%s: %s", custom_error, message)
    return custom_error
