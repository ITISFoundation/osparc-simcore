"""
Service layer for scicrunch research resources operations
"""

import logging

from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from pydantic import HttpUrl, ValidationError

from ._client import SciCrunch
from ._repository import ScicrunchResourcesRepository
from .models import ResearchResource, ResearchResourceAtdB, ResourceHit

_logger = logging.getLogger(__name__)


class ScicrunchResourcesService:
    """Service layer handling business logic for scicrunch resources.

    - Research Resources operations (RRID = Research Resource ID)
    """

    def __init__(self, repo: ScicrunchResourcesRepository, client: SciCrunch):
        self._repo = repo
        # client to interact with scicrunch.org service
        self._client = client

    async def list_research_resources(self) -> list[ResearchResource]:
        """List all research resources as domain models."""
        rows = await self._repo.list_all_resources()
        if not rows:
            return []

        resources = []
        for row in rows:
            try:
                resource_data = dict(row)
                resource = ResearchResource.model_validate(resource_data)
                resources.append(resource)
            except ValidationError as err:
                _logger.warning(
                    **create_troubleshooting_log_kwargs(
                        f"Invalid data for resource {row.rrid}",
                        error=err,
                        error_context={"row_data": dict(row)},
                    )
                )
                continue

        return resources

    async def get_research_resource(self, rrid: str) -> ResearchResource | None:
        """Get resource as domain model."""
        resource_atdb = await self.get_resource_atdb(rrid)
        if not resource_atdb:
            return None

        try:
            return ResearchResource.model_validate(resource_atdb.model_dump())
        except ValidationError as err:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Failed to convert resource {rrid} to domain model",
                    error=err,
                    error_context={
                        "rrid": rrid,
                        "resource_data": resource_atdb.model_dump(),
                    },
                )
            )
            return None

    async def get_or_fetch_research_resource(self, rrid: str) -> ResearchResource:
        """Get resource from database first, fetch from SciCrunch API if not found."""
        # Validate the RRID format first
        validated_rrid = SciCrunch.validate_identifier(rrid)

        # Check if in database first
        resource = await self.get_research_resource(validated_rrid)
        if resource:
            return resource

        # Otherwise, request from scicrunch service
        return await self._client.get_resource_fields(validated_rrid)

    async def get_resource_atdb(self, rrid: str) -> ResearchResourceAtdB | None:
        """Get resource with all database fields."""
        row = await self._repo.get_resource_by_rrid(rrid)
        if not row:
            return None

        try:
            return ResearchResourceAtdB.model_validate(dict(row))
        except ValidationError as err:
            _logger.exception(
                **create_troubleshooting_log_kwargs(
                    f"Invalid data for resource {rrid}",
                    error=err,
                    error_context={"rrid": rrid, "row_data": dict(row)},
                )
            )
            return None

    async def search_research_resources(self, guess_name: str) -> list[ResourceHit]:
        """Search for research resources using SciCrunch API."""
        guess_name = guess_name.strip()
        if not guess_name:
            return []

        return await self._client.search_resource(guess_name)

    async def create_research_resource(self, rrid: str) -> ResearchResource:
        """Add a research resource by RRID, fetching from SciCrunch if not in database."""
        # Check if exists in database first
        resource = await self.get_research_resource(rrid)
        if resource:
            return resource

        # If not found, request from scicrunch service
        resource = await self._client.get_resource_fields(rrid)

        # Insert new or update if exists
        return await self.upsert_research_resource(resource)

    async def upsert_research_resource(
        self, resource: ResearchResource
    ) -> ResearchResource:
        """Create or update a research resource."""
        values = resource.model_dump(exclude_unset=True)
        row = await self._repo.upsert_resource(values)
        return ResearchResource.model_validate(dict(row))

    # HELPERS --

    def get_resolver_web_url(self, rrid: str) -> HttpUrl:
        """Get the resolver web URL for a given RRID."""
        return self._client.get_resolver_web_url(rrid)
