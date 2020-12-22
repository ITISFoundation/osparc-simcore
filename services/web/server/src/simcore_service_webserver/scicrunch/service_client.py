"""
    Layer to interact with with scicrunch service API (https://scicrunch.org/api/)

    - http client for API requests
    - Error handling:
        - translates network errors
        - translates request error codes

"""

import logging
from enum import IntEnum
from http import HTTPStatus
from typing import Any, Dict, List, MutableMapping, Optional

import aiohttp
from aiohttp import ClientSession, web
from aiohttp.web_exceptions import HTTPBadRequest, HTTPPaymentRequired, HTTPUnauthorized
from pydantic import ValidationError
from servicelib.client_session import get_client_session
from yarl import URL

from ._config import SciCrunchSettings
from .scicrunch_models import (
    ListOfResourceHits,
    ResourceHit,
    ResourceView,
    normalize_rrid_tags,
)

logger = logging.getLogger(__name__)


## RAW REQUESTS  ------

#
# Free functions with raw request scicrunch.org API
#    - client request context
#    - raise_for_status=True -> Raise an aiohttp.ClientResponseError if the response status is 400 or higher
#    - validates response and prunes using pydantic models


async def get_all_versions(
    unprefixed_rrid: str, client: ClientSession, settings: SciCrunchSettings
) -> List[Dict[str, Any]]:
    async with client.get(
        f"{settings.api_base_url}/resource/versions/all/{unprefixed_rrid}",
        params={"key": settings.api_key.get_secret_value()},
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        return body.get("data") if body.get("success") else []


async def get_resource_fields(
    rrid: str, client: ClientSession, settings: SciCrunchSettings
) -> ResourceView:
    async with client.get(
        f"{settings.api_base_url}/resource/fields/view/{rrid}",
        params={"key": settings.api_key.get_secret_value()},
        raise_for_status=True,
    ) as resp:
        body = await resp.json()

        assert body.get("success")  # nosec
        return ResourceView(**body.get("data", {}))


async def autocomplete_by_name(
    guess_name: str, client: ClientSession, settings: SciCrunchSettings
) -> ListOfResourceHits:
    async with client.get(
        f"{settings.api_base_url}/resource/fields/autocomplete",
        params={
            "key": settings.api_key.get_secret_value(),
            "field": "Resource Name",
            "value": guess_name.strip(),
        },
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        assert body.get("success")  # nosec
        return ListOfResourceHits.parse_obj(body.get("data", []))


## ERROR  ------


class ScicrunchServiceError(Exception):
    # service down
    # requests time-out
    pass


class ScicrunchConfigError(Exception):
    # wrong token?
    # wrong formatting?
    # service API changed?
    pass


def map_to_web_exception(error: aiohttp.ClientResponseError) -> web.HTTPError:
    # gets here aiohttp.ClientResponseError raisen when the response from scicrunch.org status is 400 or higher
    assert 400 <= error.status < 600, error.status  # nosec

    # error.request_info
    # error.status
    # error.message

    if error.status == HTTPBadRequest.status_code:
        # problem with our data
        pass

    elif error.status == HTTPUnauthorized.status_code:
        # might not have correct cookie?
        pass

    elif HTTPPaymentRequired.status_code:
        pass

    elif error.status >= 500:  # scicrunch.org server error
        web_error = web.HTTPServiceUnavailable(
            reason=f"scicrunch.org cannot perform our requests: {error.message}"
        )

    return web_error


## THICK CLIENT  ------


class ValidationResult(IntEnum):
    UNKNOWN = -1
    INVALID = 0
    VALID = 1


class SciCrunch:
    """Client to communicate with scicrunch.org service

    - wraps all calls to scicrunch.org API
        - return result or raises web.HTTPError
    - one instance per application
        - uses app aiohttp client session instance
        - uses settings
    """

    # FIXME: scicrunch timeouts should raise -> Service not avialable with a msg that scicrunch is currently not responding

    def __init__(self, client: ClientSession, settings: SciCrunchSettings):
        self.settings = settings
        self.client = client
        self.base_url = URL.build(
            scheme=self.settings.api_base_url.scheme,
            host=self.settings.api_base_url.host,
        )

        self.portal_site_url = str(self.base_url.with_path("/resources/"))
        self.new_submission_site_url = str(
            self.base_url.with_path("/resources/about/resource")
        )

    # Website links ---------

    def get_rrid_link(self, rrid: str) -> str:
        # NOTE: for some reason scicrunch query does not like prefix!
        return str(
            self.base_url.with_path("/resources/Any/search").with_query(
                q="undefined", l=rrid.replace("RRID: ", "").strip()
            )
        )

    # Application instance ---------

    @classmethod
    def acquire_instance(
        cls, app: MutableMapping[str, Any], settings: SciCrunchSettings
    ) -> "SciCrunch":
        """ Returns single instance for the application and stores it """
        obj = app.get(f"{__name__}.SciCrunchClient")
        if obj is None:
            session = get_client_session(app)
            app[f"{__name__}.SciCrunchClient"] = obj = cls(session, settings)
        return obj

    @staticmethod
    def get_instance(app: MutableMapping[str, Any]) -> Optional["SciCrunch"]:
        obj = app.get(f"{__name__}.SciCrunchClient")
        if obj is None:
            raise web.HTTPServiceUnavailable(
                reason="Services on scicrunch.org are currently disabled"
            )
        return obj

    # API calls --------

    @classmethod
    def validate_identifier(cls, rrid: str) -> str:
        try:
            return normalize_rrid_tags(rrid)
        except ValueError:
            raise web.HTTPUnprocessableEntity(
                reason=f"Invalid format for an RRID '{rrid}'"
            )

    async def validate_resource(self, rrid: str) -> ValidationResult:
        try:
            rrid = self.validate_identifier(rrid)
            versions = await get_all_versions(rrid, self.client, self.settings)
            return ValidationResult.VALID if versions else ValidationResult.INVALID

        except aiohttp.ClientResponseError as err:
            if err.status == HTTPStatus.BAD_REQUEST:
                return ValidationResult.INVALID
            return ValidationResult.UNKNOWN

        except aiohttp.ClientError:
            # connection handling and server response misbehaviors
            # ClientResposeError over 300
            # raises? --> does NOT mean it is invalid but that cannot determine validity right now!!!
            # - server not reachable: down, wrong address
            # - timeout: server slowed down (retry?)
            return ValidationResult.UNKNOWN

        except (ValidationError):
            logger.debug("Validation error of RRID: %s", rrid, exc_info=True)
            return ValidationResult.INVALID

    async def get_resource_fields(self, rrid: str) -> ResourceView:
        try:
            rrid = self.validate_identifier(rrid)
            resource_view = await get_resource_fields(rrid, self.client, self.settings)
            return resource_view

        except aiohttp.ClientResponseError as err:
            raise map_to_web_exception

        except (aiohttp.ClientError, ValidationError):
            logger.debug(
                "Failed to get fields for resource RRID: %s", rrid, exc_info=True
            )
            raise web.HTTPNotFound(
                reason=f"Cannot find a valid research resource for RRID {rrid}"
            )

    async def search_resource(self, name_as: str) -> ListOfResourceHits:
        try:
            # FIXME: timeout for this should be larger than standard
            return await autocomplete_by_name(name_as, self.client, self.settings)
        except (aiohttp.ClientError, ValidationError):
            logger.debug("Failed to autocomplete : %s", name_as)
        return ListOfResourceHits(__root__=[])
