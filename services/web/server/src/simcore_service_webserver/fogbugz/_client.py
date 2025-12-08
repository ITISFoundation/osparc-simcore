"""Interface to communicate with Fogbugz API

- Simple client to create cases in Fogbugz
"""

import json
import logging
from typing import Any, Final
from urllib.parse import urljoin

import httpx
from aiohttp import web
from pydantic import AnyUrl, BaseModel, Field, SecretStr
from servicelib.aiohttp import status
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from ..products import products_service
from ..products.models import Product
from .settings import get_plugin_settings

_logger = logging.getLogger(__name__)

_JSON_CONTENT_TYPE = "application/json"
_UNKNOWN_ERROR_MESSAGE = "Unknown error occurred"


class FogbugzClientBaseError(Exception):
    """Base exception class for Fogbugz client errors"""


class FogbugzCaseCreate(BaseModel):
    fogbugz_project_id: int = Field(description="Project ID in Fogbugz")
    title: str = Field(description="Case title")
    description: str = Field(description="Case description/first comment")


def _should_retry(response: httpx.Response | None) -> bool:
    if response is None:
        return True
    return (
        response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR
        or response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    )


class FogbugzRestClient:
    """REST client for Fogbugz API"""

    def __init__(self, api_token: SecretStr, base_url: AnyUrl) -> None:
        self._client = httpx.AsyncClient()
        self._api_token = api_token
        self._base_url = base_url

    async def _make_api_request(self, json_payload: dict[str, Any]) -> dict[str, Any]:
        """Make a request to Fogbugz API with common formatting"""

        @retry(
            retry=(
                retry_if_result(_should_retry)
                | retry_if_exception_type(
                    (
                        httpx.ConnectError,
                        httpx.TimeoutException,
                        httpx.NetworkError,
                        httpx.ProtocolError,
                    )
                )
            ),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _request() -> httpx.Response:
            # Fogbugz requires multipart/form-data with stringified JSON
            files = {"request": (None, json.dumps(json_payload), _JSON_CONTENT_TYPE)}
            url = urljoin(f"{self._base_url}", "f/api/0/jsonapi")

            return await self._client.post(url, files=files)

        try:
            response = await _request()
            response.raise_for_status()
            response_data: dict[str, Any] = response.json()
            return response_data
        except Exception:
            _logger.error(  # noqa: TRY400
                "Failed to make API request to Fogbugz with payload: %s", json_payload
            )
            raise

    async def create_case(self, data: FogbugzCaseCreate) -> str:
        """Create a new case in Fogbugz"""
        json_payload = {
            "cmd": "new",
            "token": self._api_token.get_secret_value(),
            "ixProject": f"{data.fogbugz_project_id}",
            "sTitle": data.title,
            "sEvent": data.description,
        }

        response_data = await self._make_api_request(json_payload)

        # Fogbugz API returns case ID in the response
        case_id = response_data.get("data", {}).get("case", {}).get("ixBug", None)
        if case_id is None:
            msg = "Failed to create case in Fogbugz"
            raise FogbugzClientBaseError(msg)

        return str(case_id)

    async def resolve_case(self, case_id: str) -> None:
        """Resolve a case in Fogbugz"""
        json_payload = {
            "cmd": "resolve",
            "token": self._api_token.get_secret_value(),
            "ixBug": case_id,
        }

        response_data = await self._make_api_request(json_payload)

        # Check if the operation was successful
        if response_data.get("error"):
            error_msg = response_data.get("error", _UNKNOWN_ERROR_MESSAGE)
            msg = f"Failed to resolve case in Fogbugz: {error_msg}"
            raise FogbugzClientBaseError(msg)

    async def get_case_status(self, case_id: str) -> str:
        """Get the status of a case in Fogbugz"""
        json_payload = {
            "cmd": "search",
            "token": self._api_token.get_secret_value(),
            "q": case_id,
            "cols": "sStatus",
        }

        response_data = await self._make_api_request(json_payload)

        # Check if the operation was successful
        if response_data.get("error"):
            error_msg = response_data.get("error", _UNKNOWN_ERROR_MESSAGE)
            msg = f"Failed to get case status from Fogbugz: {error_msg}"
            raise FogbugzClientBaseError(msg)

        # Extract the status from the search results
        cases = response_data.get("data", {}).get("cases", [])
        if not cases:
            msg = f"Case {case_id} not found in Fogbugz"
            raise FogbugzClientBaseError(msg)

        # Find the case with matching ixBug
        target_case = None
        for case in cases:
            if str(case.get("ixBug")) == str(case_id):
                target_case = case
                break

        if target_case is None:
            msg = f"Case {case_id} not found in search results"
            raise FogbugzClientBaseError(msg)

        # Get the status from the found case
        _status: str = target_case.get("sStatus", "")
        if not _status:
            msg = f"Status not found for case {case_id}"
            raise FogbugzClientBaseError(msg)

        return _status

    async def reopen_case(
        self, case_id: str, assigned_fogbugz_person_id: str, reopen_msg: str = ""
    ) -> None:
        """Reopen a case in Fogbugz (uses reactivate for resolved cases, reopen for closed cases)"""
        # First get the current status to determine which command to use
        current_status = await self.get_case_status(case_id)

        # Determine the command based on current status
        if current_status.lower().startswith("active"):
            return  # Case is already active, no action needed

        if current_status.lower().startswith("resolved"):
            cmd = "reactivate"
        elif current_status.lower().startswith("closed"):
            cmd = "reopen"
        else:
            msg = f"Cannot reopen case {case_id} with status '{current_status}'. Only resolved or closed cases can be reopened."
            raise FogbugzClientBaseError(msg)

        json_payload = {
            "cmd": cmd,
            "token": self._api_token.get_secret_value(),
            "ixBug": case_id,
            "ixPersonAssignedTo": assigned_fogbugz_person_id,
            "sEvent": reopen_msg,
        }

        response_data = await self._make_api_request(json_payload)

        # Check if the operation was successful
        if response_data.get("error"):
            error_msg = response_data.get("error", _UNKNOWN_ERROR_MESSAGE)
            msg = f"Failed to reopen case in Fogbugz: {error_msg}"
            raise FogbugzClientBaseError(msg)

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - cleanup client"""
        await self._client.aclose()


_APPKEY: Final = web.AppKey(FogbugzRestClient.__name__, FogbugzRestClient)


async def setup_fogbugz_rest_client(app: web.Application) -> None:
    """Setup Fogbugz REST client"""
    settings = get_plugin_settings(app)

    # Fail fast if unexpected configuration
    products: list[Product] = products_service.list_products(app=app)
    for product in products:
        if product.support_standard_group_id is not None:
            if product.support_assigned_fogbugz_person_id is None:
                msg = (
                    f"Product '{product.name}' has support_standard_group_id set "
                    "but `support_assigned_fogbugz_person_id` is not configured."
                )
                raise FogbugzClientBaseError(msg)
            if product.support_assigned_fogbugz_project_id is None:
                msg = (
                    f"Product '{product.name}' has support_standard_group_id set "
                    "but `support_assigned_fogbugz_project_id` is not configured."
                )
                raise FogbugzClientBaseError(msg)
        else:
            _logger.info(
                "Product '%s' has support conversation disabled (therefore Fogbugz integration is not necessary for this product)",
                product.name,
            )

    client = FogbugzRestClient(
        api_token=settings.FOGBUGZ_API_TOKEN,
        base_url=settings.FOGBUGZ_URL,
    )

    app[_APPKEY] = client


def get_fogbugz_rest_client(app: web.Application) -> FogbugzRestClient:
    """Get Fogbugz REST client from app state"""
    app_key: FogbugzRestClient = app[_APPKEY]
    return app_key
