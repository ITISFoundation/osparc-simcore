"""
   Client to interact with scicrunch service (https://scicrunch.org)
    - both with REST API and resolver API

"""

import asyncio
import logging

from aiohttp import ClientSession, client_exceptions, web
from pydantic import HttpUrl, TypeAdapter, ValidationError
from servicelib.aiohttp.client_session import get_client_session
from yarl import URL

from ._resolver import ResolvedItem, resolve_rrid
from ._rest import autocomplete_by_name, get_resource_fields
from .errors import (
    InvalidRRIDError,
    ScicrunchAPIError,
    ScicrunchConfigError,
    ScicrunchServiceError,
    map_to_scicrunch_error,
)
from .models import ResearchResource, ResourceHit, normalize_rrid_tags
from .settings import SciCrunchSettings

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
        assert self.settings.SCICRUNCH_API_BASE_URL.host  # nosec
        self.base_url = URL.build(
            scheme=self.settings.SCICRUNCH_API_BASE_URL.scheme,
            host=self.settings.SCICRUNCH_API_BASE_URL.host,
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
        cls, app: web.Application, settings: SciCrunchSettings
    ) -> "SciCrunch":
        """Returns single instance for the application and stores it"""
        obj: SciCrunch | None = app.get(f"{__name__}.{cls.__name__}")
        if obj is None:
            session = get_client_session(app)
            app[f"{__name__}.{cls.__name__}"] = obj = cls(session, settings)
        return obj

    @classmethod
    def get_instance(cls, app: web.Application) -> "SciCrunch":
        obj: SciCrunch | None = app.get(f"{__name__}.{cls.__name__}")
        if obj is None:
            raise ScicrunchConfigError(
                reason="Services on scicrunch.org are currently disabled"
            )
        return obj

    # MEMBERS --------

    def get_search_web_url(self, rrid: str) -> str:
        # NOTE: for some reason scicrunch query does not like prefix!
        prefixless_rrid = rrid.replace("RRID:", "").strip()
        # example https://scicrunch.org/resources/Any/search?q=AB_90755&l=AB_90755
        return str(
            self.base_url.with_path("/resources/Any/search").with_query(
                q="undefined", l=prefixless_rrid
            )
        )

    def get_resolver_web_url(self, rrid: str) -> HttpUrl:
        # example https://scicrunch.org/resolver/RRID:AB_90755
        output: HttpUrl = TypeAdapter(HttpUrl).validate_python(
            f"{self.settings.SCICRUNCH_RESOLVER_BASE_URL}/{rrid}"
        )
        return output

    @classmethod
    def validate_identifier(cls, rrid: str, *, for_api: bool = False) -> str:
        try:
            rrid = normalize_rrid_tags(rrid, with_prefix=False)
        except ValueError as err:
            raise InvalidRRIDError(rrid=rrid) from err

        if for_api and not rrid.startswith("SCR_"):
            # "SCR" for the SciCrunch registry of tools
            # scicrunch API does not support anything else but tools (see test_scicrunch_services.py)
            raise InvalidRRIDError(
                msg_template=": only 'SCR' from scicrunch registry of tools allowed"
            )

        return rrid

    async def _get_resource_field_using_api(self, rrid: str) -> ResearchResource:
        # NOTE: This is currently replaced by 'resolve_rrid'.
        # This option uses rest API which requires authentication
        #
        rrid = self.validate_identifier(rrid, for_api=True)
        resource_view = await get_resource_fields(rrid, self.client, self.settings)

        # convert to domain model
        return ResearchResource(
            rrid=resource_view.scicrunch_id,
            name=resource_view.get_name(),
            description=resource_view.get_description(),
        )

    async def get_resource_fields(self, rrid: str) -> ResearchResource:
        try:
            # NOTE: replaces former call to API.
            # Resolver entrypoint does NOT require authentication
            # and has an associated website
            resolved_items: list[ResolvedItem] = await resolve_rrid(
                rrid, self.client, self.settings
            )
            if not resolved_items:
                raise InvalidRRIDError(msg_template=f".Could not resolve {rrid}")

            # WARNING: currently we only take the first, but it might
            # have multiple hits. Nonetheless, test_scicrunch_resolves_all_valid_rrids
            # checks them all
            resolved = resolved_items[0]

            return ResearchResource(
                rrid=rrid,
                name=resolved.name,
                description=resolved.description,
            )

        except client_exceptions.ClientResponseError as err:
            # These exceptions could happen after we get response from server
            raise map_to_scicrunch_error(rrid, err.status, err.message) from err

        except (ValidationError, client_exceptions.InvalidURL) as err:
            raise ScicrunchAPIError(
                reason="scicrunch API response unexpectedly changed"
            ) from err

        except (
            client_exceptions.ClientConnectionError,
            client_exceptions.ClientPayloadError,
            asyncio.TimeoutError,
        ) as err:
            # https://docs.aiohttp.org/en/stable/client_reference.html#hierarchy-of-exceptions
            raise ScicrunchServiceError(
                reason="Failed to connect scicrunch service"
            ) from err

    async def search_resource(self, name_as: str) -> list[ResourceHit]:
        # Safe: returns empty string if fails!
        # Might be slow and timeout!
        # Might be good to know that scicrunch.org is not reachable and cannot perform search now?
        hits = await autocomplete_by_name(name_as, self.client, self.settings)
        return hits.root
