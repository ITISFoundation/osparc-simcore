"""
   Functions and models to query scicrunch service REST API (https://scicrunch.org/api/)

    - http client for API requests
    - Error handling:
        - translates network errors
        - translates request error codes

    Free functions with raw request scicrunch.org API
    - client request context
    - raise_for_status=True -> Raise an aiohttp.ClientResponseError if the response status is 400 or higher
    - validates response and prunes using pydantic models

    SEE test_scicrunch_service_api.py
"""

import logging
from typing import Annotated, Any

from aiohttp import ClientSession
from pydantic import BaseModel, Field, RootModel
from yarl import URL

from .models import ResourceHit
from .settings import SciCrunchSettings

logger = logging.getLogger(__name__)


# MODELS --
#
# NOTE: These models are a trucated version of the data payload for a scicrunch response.#
# NOTE: Examples of complete responses can be found in test_scicrunch.py::mock_scicrunch_service_api
#


class FieldItem(BaseModel):
    field_name: str = Field(..., alias="field")
    required: bool
    value: str | None | list[Any] = None


class ResourceView(BaseModel):
    resource_fields: Annotated[list[FieldItem], Field([], alias="fields")]
    version: int
    curation_status: str
    last_curated_version: int
    scicrunch_id: str

    @classmethod
    def from_response_payload(cls, payload: dict):
        assert payload["success"] is True  # nosec
        return cls(**payload["data"])

    @property
    def is_curated(self) -> bool:
        return self.curation_status.lower() == "curated"

    def _get_field(self, fieldname: str):
        for field in self.resource_fields:
            if field.field_name == fieldname:
                return field.value
        msg = f"Cannot file expected field {fieldname}"
        raise ValueError(msg)

    def get_name(self):
        return str(self._get_field("Resource Name"))

    def get_description(self):
        return str(self._get_field("Description"))

    def get_resource_url(self):
        return URL(str(self._get_field("Resource URL")))


class ListOfResourceHits(RootModel[list[ResourceHit]]):
    ...


# REQUESTS


async def get_all_versions(
    unprefixed_rrid: str, client: ClientSession, settings: SciCrunchSettings
) -> list[dict[str, Any]]:
    async with client.get(
        f"{settings.SCICRUNCH_API_BASE_URL}/resource/versions/all/{unprefixed_rrid}",
        params={"key": settings.SCICRUNCH_API_KEY.get_secret_value()},
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        output: list[dict[str, Any]] = body.get("data") if body.get("success") else []
        return output


async def get_resource_fields(
    rrid: str, client: ClientSession, settings: SciCrunchSettings
) -> ResourceView:
    async with client.get(
        f"{settings.SCICRUNCH_API_BASE_URL}/resource/fields/view/{rrid}",
        params={"key": settings.SCICRUNCH_API_KEY.get_secret_value()},
        raise_for_status=True,
    ) as resp:
        body = await resp.json()

        assert body.get("success")  # nosec
        return ResourceView(**body.get("data", {}))


async def autocomplete_by_name(
    guess_name: str, client: ClientSession, settings: SciCrunchSettings
) -> ListOfResourceHits:
    async with client.get(
        f"{settings.SCICRUNCH_API_BASE_URL}/resource/fields/autocomplete",
        params={
            "key": settings.SCICRUNCH_API_KEY.get_secret_value(),
            "field": "Resource Name",
            "value": guess_name.strip(),
        },
        raise_for_status=True,
    ) as resp:
        body = await resp.json()
        assert body.get("success")  # nosec
        return ListOfResourceHits.model_validate(body.get("data", []))
