"""
Service layer for scicrunch research resources operations
"""

import logging

from aiohttp import web
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from pydantic import ValidationError

from ._repository import ScicrunchResourcesRepository
from .models import ResearchResource, ResearchResourceAtdB

_logger = logging.getLogger(__name__)


class ScicrunchResourcesService:
    """Service layer handling business logic for scicrunch resources."""

    def __init__(self, app: web.Application):
        self.app = app
        self._repo = ScicrunchResourcesRepository.create_from_app(app)

    async def list_resources(self) -> list[ResearchResource]:
        """List all research resources as domain models."""
        rows = await self._repo.list_all_resources()
        if not rows:
            return []

        resources = []
        for row in rows:
            try:
                resource = ResearchResource.model_validate(dict(row))
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

    async def get_resource(self, rrid: str) -> ResearchResource | None:
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

    async def upsert_resource(self, resource: ResearchResource) -> ResearchResource:
        """Create or update a research resource."""
        values = resource.model_dump(exclude_unset=True)
        row = await self._repo.upsert_resource(values)
        return ResearchResource.model_validate(dict(row))
