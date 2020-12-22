"""
    Layer to interact with with scicrunch service API (https://scicrunch.org/api/)

    - http client for API requests
    - Error handling:
        - translates network errors
        - translates request error codes

"""

import logging
from contextlib import suppress
from typing import Any, Dict, List, MutableMapping, Optional

from aiohttp import ClientSession, client_exceptions, web_exceptions
from pydantic import ValidationError
from servicelib.client_session import get_client_session
from yarl import URL

from ._config import SciCrunchSettings
from .scicrunch_models import (
    ListOfResourceHits,
    ResearchResource,
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
#
# SEE test_scicrunch_service.py


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
    # NOTE: error handling designed based on test_scicrunch_service.py
    assert 400 <= error_code < 600, error_code  # nosec

    custom_error = ScicrunchError("Unexpected error in scicrunch.org")

    if error_code in (
        web_exceptions.HTTPBadRequest.status_code,
        web_exceptions.HTTPNotFound.status_code,
    ):
        raise InvalidRRID(rrid)

    elif error_code == web_exceptions.HTTPUnauthorized.status_code:
        # might not have correct cookie?
        custom_error = ScicrunchConfigError("scicrunch.org authentication failed")

    elif error_code >= 500:  # scicrunch.org server error
        custom_error = ScicrunchServiceError(
            "scicrunch.org cannot perform our requests"
        )

    logger.error("%s: %s", custom_error, message)
    return custom_error


## THICK CLIENT  ------


class SciCrunch:
    """Proxy object to interact with scicrunch.org service

    - wraps all requests to scicrunch.org API
        - return domain models or raises ScicrunchError

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

    # Application instance ---------
    #  - Ensures a single instance inside an application
    # TODO: this can be added using a policy class decorator

    @classmethod
    def acquire_instance(
        cls, app: MutableMapping[str, Any], settings: SciCrunchSettings
    ) -> "SciCrunch":
        """ Returns single instance for the application and stores it """
        obj = app.get(f"{__name__}.{cls.__name__}")
        if obj is None:
            session = get_client_session(app)
            app[f"{__name__}.{cls.__name__}"] = obj = cls(session, settings)
        return obj

    @classmethod
    def get_instance(cls, app: MutableMapping[str, Any]) -> Optional["SciCrunch"]:
        obj = app.get(f"{__name__}.{cls.__name__}")
        if obj is None:
            raise ScicrunchConfigError(
                reason="Services on scicrunch.org are currently disabled"
            )
        return obj

    # MEMBERS --------

    def get_rrid_link(self, rrid: str) -> str:
        # NOTE: for some reason scicrunch query does not like prefix!
        return str(
            self.base_url.with_path("/resources/Any/search").with_query(
                q="undefined", l=rrid.replace("RRID: ", "").strip()
            )
        )

    @classmethod
    def validate_identifier(cls, rrid: str) -> str:
        try:
            rrid = normalize_rrid_tags(rrid, with_prefix=False)
        except ValueError:
            raise InvalidRRID(rrid)

        # "SCR" for the SciCrunch registry of tools
        if rrid.startswith("SCR"):
            # scicrunch API does not support anything else but tools (see test_scicrunch_services.py)
            raise InvalidRRID(": only 'SCR' from scicrunch registry of tools allowed")
        return rrid

    async def get_resource_fields(self, rrid: str) -> ResearchResource:
        try:
            rrid = self.validate_identifier(rrid)
            resource_view = await get_resource_fields(rrid, self.client, self.settings)
            # convert to domain model
            return ResearchResource(
                rrid=resource_view.scicrunch_id,
                name=resource_view.get_name(),
                description=resource_view.get_description(),
            )

        except client_exceptions.ClientResponseError as err:
            # These exceptions could happen after we get response from server
            raise map_to_scicrunch_error(rrid, err.status, err.message) from err

        except (ValidationError, client_exceptions.InvalidURL) as err:
            raise ScicrunchAPIError(
                "scicrunch API response unexpectedly changed"
            ) from err

        except (
            client_exceptions.ClientConnectionError,
            client_exceptions.ClientPayloadError,
        ) as err:
            # https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
            raise ScicrunchServiceError("Failed to connect scicrunch service") from err

    async def search_resource(self, name_as: str) -> List[ResourceHit]:
        # Safe: returns empty string if fails!
        # Might be slow and timeout!
        with suppress(Exception):
            hits = await autocomplete_by_name(name_as, self.client, self.settings)
            return hits.__root__

        return []
