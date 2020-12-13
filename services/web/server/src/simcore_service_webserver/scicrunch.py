"""
    Models and client calls to K-Core's scicrunch API (https://scicrunch.org/api/)
"""
# TODO: not happy at all with this!!


import logging
import re
from enum import IntEnum
from http import HTTPStatus
from typing import Any, List, MutableMapping, Optional, Union
from uuid import UUID

import aiohttp
from aiohttp import ClientSession
from pydantic import BaseModel, BaseSettings, Field, HttpUrl, SecretStr, ValidationError
from servicelib.client_session import get_client_session

logger = logging.getLogger(__name__)


## SETTINGS -------------


class SciCrunchSettings(BaseSettings):
    api_base_url: HttpUrl = "https://scicrunch.org/api/1"
    api_key: SecretStr  # Login in https://scicrunch.org and get API Key under My Account -> API Keys

    class Config:
        env_prefix = "CSICRUNCH_"


## MODELS -------------


# NOTE: there is no need to capture everything
#
# fields = [
#   {
#     "field": "Resource Name",
#     "required": true,
#     "type": "text",
#     "max_number": "1",
#     "value": "Jupyter Notebook",
#     "position": 0,
#     "display": "title",
#     "alt": "The name of the unique resource you are submitting"
#   }, ...
# ]
class FieldItem(BaseModel):
    field_name: str = Field(..., alias="field")
    required: bool
    # field_type: str = Field(..., alias="type") # text, textarea, resource-types, ...
    # max_number: str  # convertable to int
    value: Union[str, None, List[Any]] = None
    # position: int
    # display: str  # title, descripiotn, url, text, owner-text
    alt: str  # alternative text


# NOTE: Response looks like
# {
#   "data": {
#     "fields": [ ... ]
#     "version": 2,
#     "curation_status": "Curated",
#     "last_curated_version": 2,
#     "scicrunch_id": "SCR_018315",
#     "original_id": "SCR_018315",
#     "image_src": null,
#     "uuid": "0e88ffa5-752f-5ae6-aab1-b350edbe2ccc",
#     "typeID": 1
#   },
#   "success": true
# }
class ResourceView(BaseModel):
    resource_fields: Optional[List[FieldItem]] = Field(None, alias="fields")
    version: int
    curation_status: str
    last_curated_version: int
    uuid: UUID
    # typeID: int
    image_src: Optional[str] = None
    scicrunch_id: str
    original_id: str

    @property
    def is_curated(self) -> bool:
        return self.curation_status.lower() == "curated"


## CLIENT CALLS -------------


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

    async def get_resource_fields(self, rrid: str) -> Optional[ResourceView]:
        try:
            rrid = self.validate_identifier(rrid)
            resource_view = await get_resource_fields(rrid, self.client, self.settings)
            return resource_view
        except (aiohttp.ClientError, ValidationError, ValueError):
            logger.debug(
                "Failed to get fields for resource RRID: %s", rrid, exc_info=True
            )
            return None


def setup_scicrunch(app: MutableMapping[str, Any]):
    try:
        settings = SciCrunchSettings()
        SciCrunchAPI.create_instance(app, settings)
    except ValidationError:
        # TODO: this means we cannot communicate with scicrunch! This service is therefore NOT available
        pass
