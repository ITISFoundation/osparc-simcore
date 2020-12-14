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

from .scicrunch_config import SciCrunchSettings
from .scicrunch_models import ResourceView

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
        assert body.get("success")
        return ResourceView(**body.get("data", {}))


# async def autocomplete_by_name(rrid: str) -> List:
#     pass


class ValidationResult(IntEnum):
    UNKNOWN = -1
    INVALID = 0
    VALID = 1


class SciCrunchAPI:
    """
    - wraps requests to scicrunch.org API
        - return result or raises web.HTTPError
    - one instance per application
        - uses app aiohttp client session instance
        - uses settings
    """

    # FIXME: From https://scicrunch.org/resources: To ensure they are recognizable, unique, and traceable,
    # identifiers are prefixed with " RRID: ", followed by a second tag that indicates the source authority that provided it
    # (e.g. "AB" for the Antibody Registry, "CVCL" for the Cellosaurus, "MMRRC" for Mutant Mouse Regional Resource Centers, "SCR"
    # for the SciCrunch registry of tools).
    # TODO: read https://www.force11.org/group/resource-identification-initiative
    RRID_RE = re.compile(r"(RRID:)?\s*(SCR_\d+)")

    def __init__(self, client: ClientSession, settings: SciCrunchSettings):
        self.settings = settings
        self.client = client

    @classmethod
    def create_instance(
        cls, app: MutableMapping[str, Any], settings: SciCrunchSettings
    ) -> "SciCrunchAPI":
        """ Creates single instance for the application and stores it """
        obj = cls.get_instance(app)
        if not obj:
            session = get_client_session(app)
            app[f"{__name__}.SciCrunchAPI"] = obj = cls(session, settings)
        return obj

    @staticmethod
    def get_instance(app: MutableMapping[str, Any]) -> Optional["SciCrunchAPI"]:
        """ Get's application instance """
        return app.get(f"{__name__}.SciCrunchAPI")

    @classmethod
    def validate_identifier(cls, rrid: str) -> str:
        match = cls.RRID_RE.match(rrid.strip())
        if match:
            return match.group(1)
        raise ValueError(f"Does not match a RRID {rrid}")

    async def validate_rrid(self, rrid: str) -> ValidationResult:
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

        except (ValidationError, ValueError):
            logger.debug("Validation error of RRID: %s", rrid, exc_info=True)
            return ValidationResult.INVALID

    async def get_resource_fields(self, rrid: str) -> ResourceView:
        try:
            rrid = self.validate_identifier(rrid)
            resource_view = await get_resource_fields(rrid, self.client, self.settings)
            return resource_view
        except (aiohttp.ClientError, ValidationError, ValueError):
            logger.debug(
                "Failed to get fields for resource RRID: %s", rrid, exc_info=True
            )
            raise web.HTTPNotFound(
                reason=r"Cannot find a valid research resource for RRID {rrid}"
            )
