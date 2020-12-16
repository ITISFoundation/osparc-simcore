"""
    http client to communicate with scicrunch API (https://scicrunch.org/api/)
"""

import logging
import re
from enum import IntEnum
from http import HTTPStatus
from typing import Any, List, MutableMapping, Optional

import aiohttp
from aiohttp import ClientSession, web
from pydantic import ValidationError
from servicelib.client_session import get_client_session
from yarl import URL

from .scicrunch_config import RRID_PATTERN, SciCrunchSettings
from .scicrunch_models import ListOfResourceHits, ResourceView

logger = logging.getLogger(__name__)


async def get_all_versions(
    rrid: str, client: ClientSession, settings: SciCrunchSettings
) -> List:
    async with client.get(
        f"{settings.api_base_url}/resource/versions/all/{rrid}",
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


class ValidationResult(IntEnum):
    UNKNOWN = -1
    INVALID = 0
    VALID = 1


class SciCrunchAPI:
    """Instance to communicate with scicrunch.org service

    - wraps all calls to scicrunch.org API
        - return result or raises web.HTTPError
    - one instance per application
        - uses app aiohttp client session instance
        - uses settings
    """

    RRID_RE = re.compile(RRID_PATTERN)

    def __init__(self, client: ClientSession, settings: SciCrunchSettings):
        self.settings = settings
        self.client = client
        self.base_url = URL.build(
            scheme=self.settings.api_base_url.scheme,
            host=self.settings.api_base_url.host,
        )

    # Website links ---------

    def get_portal_link(self) -> str:
        return str(self.base_url.with_path("/resources/"))

    def get_rrid_link(self, rrid: str) -> str:
        return str(
            self.base_url.with_path("/resources/Any/search").with_query(
                q="undefined", l=rrid
            )
        )

    def get_new_submission_link(self) -> str:
        return str(self.base_url.with_path("/resources/about/resource"))

    # Application instance ---------

    @classmethod
    def acquire_instance(
        cls, app: MutableMapping[str, Any], settings: SciCrunchSettings
    ) -> "SciCrunchAPI":
        """ Returns single instance for the application and stores it """
        obj = cls.get_instance(app)
        if obj is None:
            session = get_client_session(app)
            app[f"{__name__}.SciCrunchAPI"] = obj = cls(session, settings)
        return obj

    @staticmethod
    def get_instance(
        app: MutableMapping[str, Any], *, raises=False
    ) -> Optional["SciCrunchAPI"]:
        """ Get's application instance """
        obj = app.get(f"{__name__}.SciCrunchAPI")
        if raises and obj is None:
            raise web.HTTPServiceUnavailable(
                reason="Link to scicrunch.org services is currently disabled."
            )
        return obj

    # API calls --------

    @classmethod
    def validate_identifier(cls, rrid: str) -> str:
        match = cls.RRID_RE.match(rrid.strip())
        if match:
            rrid = match.group(2)  # WARNING: captures indexing is 1-based
            assert rrid and isinstance(rrid, str), "Captured {rrid}"  # nosec
            return rrid

        raise web.HTTPUnprocessableEntity(reason=f"Invalid format for an RRID '{rrid}'")

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


# FIXME: scicrunch timeouts should raise -> Service not avialable with a msg that scicrunch is currently not responding
