"""Interface to communicate with Fogbugz API

- Simple client to create cases in Fogbugz
"""

import json
import logging

import httpx
from aiohttp import web
from pydantic import BaseModel, Field

from ..products import products_service
from ..products.models import Product
from .settings import FogbugzSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPE = "application/json"
_UNKNOWN_ERROR_MESSAGE = "Unknown error occurred"


class FogbugzCaseCreate(BaseModel):
    fogbugz_project_id: str = Field(description="Project ID in Fogbugz")
    title: str = Field(description="Case title")
    description: str = Field(description="Case description/first comment")


class FogbugzRestClient:
    """REST client for Fogbugz API"""

    def __init__(
        self, client: httpx.AsyncClient, api_token: str, base_url: str
    ) -> None:
        self._client = client
        self._api_token = api_token
        self._base_url = base_url

    async def create_case(self, data: FogbugzCaseCreate) -> str:
        """Create a new case in Fogbugz"""
        json_payload = {
            "cmd": "new",
            "token": self._api_token,
            "ixProject": data.fogbugz_project_id,
            "sTitle": data.title,
            "sEvent": data.description,
        }

        # Fogbugz requires multipart/form-data with stringified JSON
        files = {"request": (None, json.dumps(json_payload), _JSON_CONTENT_TYPE)}

        url = f"{self._base_url}/f/api/0/jsonapi"

        response = await self._client.post(url, files=files)
        response.raise_for_status()
        response_data = response.json()

        # Fogbugz API returns case ID in the response
        case_id = response_data.get("data", {}).get("case", {}).get("ixBug", None)
        if case_id is None:
            msg = "Failed to create case in Fogbugz"
            raise ValueError(msg)

        return str(case_id)

    async def resolve_case(self, case_id: str) -> None:
        """Resolve a case in Fogbugz"""
        json_payload = {
            "cmd": "resolve",
            "token": self._api_token,
            "ixBug": case_id,
        }

        # Fogbugz requires multipart/form-data with stringified JSON
        files = {"request": (None, json.dumps(json_payload), _JSON_CONTENT_TYPE)}

        url = f"{self._base_url}/f/api/0/jsonapi"

        response = await self._client.post(url, files=files)
        response.raise_for_status()
        response_data = response.json()

        # Check if the operation was successful
        if response_data.get("error"):
            error_msg = response_data.get("error", _UNKNOWN_ERROR_MESSAGE)
            msg = f"Failed to resolve case in Fogbugz: {error_msg}"
            raise ValueError(msg)

    async def get_case_status(self, case_id: str) -> str:
        """Get the status of a case in Fogbugz"""
        json_payload = {
            "cmd": "search",
            "token": self._api_token,
            "q": case_id,
            "cols": "sStatus",
        }

        # Fogbugz requires multipart/form-data with stringified JSON
        files = {"request": (None, json.dumps(json_payload), _JSON_CONTENT_TYPE)}

        url = f"{self._base_url}/f/api/0/jsonapi"

        response = await self._client.post(url, files=files)
        response.raise_for_status()
        response_data = response.json()

        # Check if the operation was successful
        if response_data.get("error"):
            error_msg = response_data.get("error", _UNKNOWN_ERROR_MESSAGE)
            msg = f"Failed to get case status from Fogbugz: {error_msg}"
            raise ValueError(msg)

        # Extract the status from the search results
        cases = response_data.get("data", {}).get("cases", [])
        if not cases:
            msg = f"Case {case_id} not found in Fogbugz"
            raise ValueError(msg)

        # Find the case with matching ixBug
        target_case = None
        for case in cases:
            if str(case.get("ixBug")) == str(case_id):
                target_case = case
                break

        if target_case is None:
            msg = f"Case {case_id} not found in search results"
            raise ValueError(msg)

        # Get the status from the found case
        status: str = target_case.get("sStatus", "")
        if not status:
            msg = f"Status not found for case {case_id}"
            raise ValueError(msg)

        return status

    async def reopen_case(self, case_id: str, assigned_fogbugz_person_id: str) -> None:
        """Reopen a case in Fogbugz (uses reactivate for resolved cases, reopen for closed cases)"""
        # First get the current status to determine which command to use
        current_status = await self.get_case_status(case_id)

        # Determine the command based on current status
        if current_status.lower().startswith("resolved"):
            cmd = "reactivate"
        elif current_status.lower().startswith("closed"):
            cmd = "reopen"
        else:
            msg = f"Cannot reopen case {case_id} with status '{current_status}'. Only resolved or closed cases can be reopened."
            raise ValueError(msg)

        json_payload = {
            "cmd": cmd,
            "token": self._api_token,
            "ixBug": case_id,
            "ixPersonAssignedTo": assigned_fogbugz_person_id,
        }

        # Fogbugz requires multipart/form-data with stringified JSON
        files = {"request": (None, json.dumps(json_payload), _JSON_CONTENT_TYPE)}

        url = f"{self._base_url}/f/api/0/jsonapi"

        response = await self._client.post(url, files=files)
        response.raise_for_status()
        response_data = response.json()

        # Check if the operation was successful
        if response_data.get("error"):
            error_msg = response_data.get("error", _UNKNOWN_ERROR_MESSAGE)
            msg = f"Failed to reopen case in Fogbugz: {error_msg}"
            raise ValueError(msg)


_APP_KEY = f"{__name__}.{FogbugzRestClient.__name__}"


async def setup_fogbugz_rest_client(app: web.Application) -> None:
    """Setup Fogbugz REST client"""
    settings: FogbugzSettings | None = get_plugin_settings(app)

    if settings is None:
        _logger.warning("Fogbugz settings not configured, skipping setup")
        return

    # Fail fast if unexpected configuration
    products: list[Product] = products_service.list_products(app=app)
    for product in products:
        if product.support_standard_group_id is not None:
            if product.support_assigned_fogbugz_person_id is None:
                msg = (
                    f"Product '{product.name}' has support_standard_group_id set "
                    "but `support_assigned_fogbugz_person_id` is not configured."
                )
                raise ValueError(msg)
            if product.support_assigned_fogbugz_project_id is None:
                msg = (
                    f"Product '{product.name}' has support_standard_group_id set "
                    "but `support_assigned_fogbugz_project_id` is not configured."
                )
                raise ValueError(msg)
        else:
            _logger.info(
                "Product '%s' has support conversation disabled (therefore Fogbugz integration is not necessary for this product)",
                product.name,
            )

    httpx_client = httpx.AsyncClient()
    client = FogbugzRestClient(
        client=httpx_client,
        api_token=settings.FOGBUGZ_API_TOKEN,
        base_url=settings.FOGBUGZ_URL,
    )

    app[_APP_KEY] = client


def get_fogbugz_rest_client(app: web.Application) -> FogbugzRestClient:
    """Get Fogbugz REST client from app state"""
    app_key: FogbugzRestClient = app[_APP_KEY]
    return app_key
