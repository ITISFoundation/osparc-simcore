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
    resource_name_as: str, client: ClientSession, settings: SciCrunchSettings
) -> ListOfResourceHits:
    async with client.get(
        f"{settings.api_base_url}/resource/fields/autocomplete",
        params={
            "key": settings.api_key.get_secret_value(),
            "field": "Resource Name",
            "value": resource_name_as,
        },
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        assert body.get("success")  # nosec
        return ListOfResourceHits(__root__=body.get("data", []))

    #
    # curl -X GET "https://scicrunch.org/api/1/resource/fields/autocomplete?field=Resource%20Name&value=octave" -H "accept: application/json
    # {
    #   "data": [
    #     {
    #       "rid": "SCR_000860",
    #       "original_id": "nlx_155680",
    #       "name": "cbiNifti: Matlab/Octave Nifti library"
    #     },
    #     {
    #       "rid": "SCR_009637",
    #       "original_id": "nlx_155924",
    #       "name": "Pipeline System for Octave and Matlab"
    #     },
    #     {
    #       "rid": "SCR_014398",
    #       "original_id": "SCR_014398",
    #       "name": "GNU Octave"
    #     }
    #   ],
    #   "success": true
    # }


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
    def acquire_instance(
        cls, app: MutableMapping[str, Any], settings: SciCrunchSettings
    ) -> "SciCrunchAPI":
        """ Returns single instance for the application and stores it """
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
                reason=f"Cannot find a valid research resource for RRID {rrid}"
            )

    async def search_resource(self, name_as: str) -> ListOfResourceHits:
        try:
            return await autocomplete_by_name(name_as, self.client, self.settings)
        except (aiohttp.ClientError, ValidationError):
            logger.debug("Failed to autocomplete : %s", name_as)
        return ListOfResourceHits(__root__=[])
