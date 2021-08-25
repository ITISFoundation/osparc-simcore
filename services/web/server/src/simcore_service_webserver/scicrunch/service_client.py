"""
   Client to interact with scicrunch service (https://scicrunch.org)
    - both with REST API and resolver API

"""

import logging
from typing import Any, List, MutableMapping

from aiohttp import ClientSession, client_exceptions
from pydantic import ValidationError
from servicelib.client_session import get_client_session
from yarl import URL

from ._config import SciCrunchSettings
from ._rest import ResourceHit, autocomplete_by_name, get_resource_fields
from .errors import (
    InvalidRRID,
    ScicrunchAPIError,
    ScicrunchConfigError,
    ScicrunchServiceError,
    map_to_scicrunch_error,
)
from .models import ResearchResource, normalize_rrid_tags

logger = logging.getLogger(__name__)


class SciCrunch:
    """Proxy object to interact with scicrunch.org service

    - wraps all requests to scicrunch.org API
        - return domain models or raises ScicrunchError-based errors

    - one instance per application
        - uses app aiohttp client session instance
        - uses settings
    """

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
        """Returns single instance for the application and stores it"""
        obj = app.get(f"{__name__}.{cls.__name__}")
        if obj is None:
            session = get_client_session(app)
            app[f"{__name__}.{cls.__name__}"] = obj = cls(session, settings)
        return obj

    @classmethod
    def get_instance(cls, app: MutableMapping[str, Any]) -> "SciCrunch":
        obj = app.get(f"{__name__}.{cls.__name__}")
        if obj is None:
            raise ScicrunchConfigError(
                reason="Services on scicrunch.org are currently disabled"
            )
        return obj

    # MEMBERS --------

    def get_rrid_link(self, rrid: str) -> str:
        # NOTE: for some reason scicrunch query does not like prefix!
        prefixless_rrid = rrid.replace("RRID:", "").strip()
        return str(
            self.base_url.with_path("/resources/Any/search").with_query(
                q="undefined", l=prefixless_rrid
            )
        )

    @classmethod
    def validate_identifier(cls, rrid: str) -> str:
        try:
            rrid = normalize_rrid_tags(rrid, with_prefix=False)
        except ValueError:
            raise InvalidRRID(rrid)

        if not rrid.startswith("SCR_"):
            # "SCR" for the SciCrunch registry of tools
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
            TimeoutError,
        ) as err:
            # https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
            raise ScicrunchServiceError("Failed to connect scicrunch service") from err

    async def search_resource(self, name_as: str) -> List[ResourceHit]:
        # Safe: returns empty string if fails!
        # Might be slow and timeout!
        # Might be good to know that scicrunch.org is not reachable and cannot perform search now?
        hits = await autocomplete_by_name(name_as, self.client, self.settings)
        return hits.__root__
