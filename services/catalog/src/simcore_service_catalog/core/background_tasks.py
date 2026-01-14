"""This background task does the following:

1. gets the full list of services from the docker registry through the director
2. gets the same list from the DB
3. if services are missing from the DB, they are added with basic access rights
    3.a. basic access rights are set as following:
        1. writable access allow the user to change meta data as well as access rights
        2. executable access allow the user to see/execute the service

"""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from pprint import pformat
from typing import Final

from fastapi import FastAPI, HTTPException
from fastapi_lifespan_manager import State
from models_library.services import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from packaging.version import Version
from pydantic import ValidationError
from sqlalchemy.exc import (
    DBAPIError,
    IntegrityError,
    OperationalError,
    SQLAlchemyError,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api._dependencies.director import get_director_client
from ..models.services_db import ServiceAccessRightsDB, ServiceMetaDataDBCreate
from ..repository.groups import GroupsRepository
from ..repository.projects import ProjectsRepository
from ..repository.services import ServicesRepository
from ..service import access_rights, manifest

_logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Categories of errors that can occur during service sync"""

    TRANSIENT = "transient"  # Network, DB connection - should retry
    PERMANENT = "permanent"  # Validation, invalid data - skip service
    CRITICAL = "critical"  # Schema issues, config errors - stop task


@dataclass
class ServiceSyncError:
    """Details of a service sync failure"""

    service_key: ServiceKey
    service_version: ServiceVersion
    error: Exception
    category: ErrorCategory
    stage: str  # e.g., "access_rights_evaluation", "database_insert"


@dataclass
class SyncReport:
    """Aggregated report of a sync run"""

    services_processed: int = 0
    services_synced: int = 0
    errors_by_category: dict[ErrorCategory, list[ServiceSyncError]] = field(default_factory=lambda: defaultdict(list))
    duration_seconds: float = 0.0

    @property
    def total_errors(self) -> int:
        return sum(len(errors) for errors in self.errors_by_category.values())

    def add_error(self, error: ServiceSyncError) -> None:
        self.errors_by_category[error.category].append(error)

    def get_summary(self) -> dict:
        """Returns structured summary for logging"""
        return {
            "services_processed": self.services_processed,
            "services_synced": self.services_synced,
            "total_errors": self.total_errors,
            "transient_errors": len(self.errors_by_category[ErrorCategory.TRANSIENT]),
            "permanent_errors": len(self.errors_by_category[ErrorCategory.PERMANENT]),
            "critical_errors": len(self.errors_by_category[ErrorCategory.CRITICAL]),
            "duration_seconds": round(self.duration_seconds, 2),
        }


def _categorize_error(error: Exception, stage: str) -> ErrorCategory:
    """Categorizes an error as transient, permanent, or critical"""

    # Transient errors: network, connection, timeout
    if isinstance(error, HTTPException):
        # Director service unavailable or network errors
        if error.status_code >= 500:
            return ErrorCategory.TRANSIENT
        # Client errors are permanent
        return ErrorCategory.PERMANENT

    if isinstance(error, (OperationalError, DBAPIError)):
        # Database connection/operational errors are transient
        return ErrorCategory.TRANSIENT

    if isinstance(error, IntegrityError):
        # Integrity errors during DB insert could be race conditions
        # These are transient if we're using proper upsert logic
        return ErrorCategory.TRANSIENT

    if isinstance(error, ValidationError):
        # Validation errors in metadata are permanent
        return ErrorCategory.PERMANENT

    if isinstance(error, SQLAlchemyError):
        # Other SQLAlchemy errors might be critical (schema issues)
        return ErrorCategory.CRITICAL

    # Unknown errors are critical
    return ErrorCategory.CRITICAL


async def _list_services_in_database(
    db_engine: AsyncEngine,
):
    services_repo = ServicesRepository(db_engine=db_engine)
    return {(service.key, service.version) for service in await services_repo.list_services()}


async def _create_services_in_database(
    app: FastAPI,
    service_keys: set[tuple[ServiceKey, ServiceVersion]],
    services_in_registry: dict[tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished],
) -> SyncReport:
    """Adds new services to the database with error classification and reporting.

    Determines the access rights of each service and adds it to the database.
    Returns a report with details about successes and failures categorized by error type.
    """
    start_time = time.time()
    report = SyncReport()
    services_repo = ServicesRepository(app.state.engine)

    def _by_version(t: tuple[ServiceKey, ServiceVersion]) -> Version:
        return Version(t[1])

    sorted_services = sorted(service_keys, key=_by_version)
    report.services_processed = len(sorted_services)

    for service_key, service_version in sorted_services:
        service_metadata: ServiceMetaDataPublished = services_in_registry[(service_key, service_version)]
        try:
            # 1. Evaluate DEFAULT ownership and access rights
            (
                owner_gid,
                service_access_rights,
            ) = await access_rights.evaluate_default_service_ownership_and_rights(
                app,
                service=service_metadata,
                product_name=app.state.default_product_name,
            )

            # 2. Inherit access rights from the latest compatible release
            inherited_data = await access_rights.inherit_from_latest_compatible_release(
                service_metadata=service_metadata,
                services_repo=services_repo,
            )

            # 3. Aggregates access rights and metadata updates
            service_access_rights += inherited_data["access_rights"]
            service_access_rights = access_rights.reduce_access_rights(service_access_rights)

            metadata_updates = {
                **service_metadata.model_dump(exclude_unset=True),
                **inherited_data["metadata_updates"],
            }

            # 4. Upsert values in database
            await services_repo.create_or_update_service(
                ServiceMetaDataDBCreate(**metadata_updates, owner=owner_gid),
                service_access_rights,
            )
            report.services_synced += 1

        except (
            HTTPException,
            ValidationError,
            OperationalError,
            DBAPIError,
            IntegrityError,
            SQLAlchemyError,
        ) as err:
            # Resilient to single failures: errors in individual (service,key)
            # should not prevent the evaluation of the rest
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6318
            stage = "database_upsert"
            if isinstance(err, (HTTPException, ValidationError)):
                stage = "access_rights_evaluation"

            category = _categorize_error(err, stage)
            sync_error = ServiceSyncError(
                service_key=service_key,
                service_version=service_version,
                error=err,
                category=category,
                stage=stage,
            )
            report.add_error(sync_error)

            # Log based on error category
            if category == ErrorCategory.PERMANENT:
                _logger.warning(
                    "Skipping service '%s:%s' due to permanent error at %s: %s",
                    service_key,
                    service_version,
                    stage,
                    err,
                )
            elif category == ErrorCategory.TRANSIENT:
                _logger.info(
                    "Transient error for service '%s:%s' at %s (will retry next cycle): %s",
                    service_key,
                    service_version,
                    stage,
                    err,
                )
            else:  # CRITICAL
                _logger.exception(
                    "Critical error for service '%s:%s' at %s",
                    service_key,
                    service_version,
                    stage,
                )

    report.duration_seconds = time.time() - start_time
    return report


async def _ensure_registry_and_database_are_synced(app: FastAPI) -> None:
    """Ensures that the services listed in the database is in sync with the registry

    Notice that a services here refers to a 2-tuple (key, version)
    """
    director_api = get_director_client(app)
    services_in_manifest_map = await manifest.get_services_map(director_api)

    services_in_db: set[tuple[ServiceKey, ServiceVersion]] = await _list_services_in_database(app.state.engine)

    # check that the db has all the services at least once
    missing_services_in_db = set(services_in_manifest_map.keys()) - services_in_db
    if missing_services_in_db:
        _logger.debug(
            "Missing services in db: %s",
            pformat(missing_services_in_db),
        )

        # update db and collect report
        report = await _create_services_in_database(app, missing_services_in_db, services_in_manifest_map)

        # Log aggregate summary
        if report.total_errors > 0:
            _logger.warning(
                "Service sync completed with errors: %s",
                pformat(report.get_summary()),
            )
            # Log details of permanent and critical errors
            for error_cat in [ErrorCategory.PERMANENT, ErrorCategory.CRITICAL]:
                for error in report.errors_by_category.get(error_cat, []):
                    _logger.info(
                        "  - %s error for %s:%s at %s: %s",
                        error.category.value,
                        error.service_key,
                        error.service_version,
                        error.stage,
                        type(error.error).__name__,
                    )
        else:
            _logger.info(
                "Service sync completed successfully: %s",
                pformat(report.get_summary()),
            )


async def _ensure_published_templates_accessible(db_engine: AsyncEngine, default_product_name: str) -> None:
    # Rationale: if a project template was published, its services must be available to everyone.
    # a published template has a column Published that is set to True
    projects_repo = ProjectsRepository(db_engine)
    published_services: set[tuple[str, str]] = {
        (service.key, service.version) for service in await projects_repo.list_services_from_published_templates()
    }

    groups_repo = GroupsRepository(db_engine)
    everyone_gid = (await groups_repo.get_everyone_group()).gid

    services_repo = ServicesRepository(db_engine)
    available_services: set[tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(gids=[everyone_gid], execute_access=True)
    }

    missing_services = published_services - available_services
    missing_services_access_rights = [
        ServiceAccessRightsDB(
            key=ServiceKey(service[0]),
            version=ServiceVersion(service[1]),
            gid=everyone_gid,
            execute_access=True,
            product_name=default_product_name,
        )
        for service in missing_services
    ]
    if missing_services_access_rights:
        _logger.info(
            "Adding access rights for published templates\n: %s",
            missing_services_access_rights,
        )
        await services_repo.upsert_service_access_rights(missing_services_access_rights)


async def _run_sync_services(app: FastAPI):
    default_product: Final[str] = app.state.default_product_name
    engine: AsyncEngine = app.state.engine

    # check that the list of services is in sync with the registry
    await _ensure_registry_and_database_are_synced(app)

    # check that the published services are available to everyone
    # (templates are published to GUESTs, so their services must be also accessible)
    await _ensure_published_templates_accessible(engine, default_product)


async def _sync_services_task(app: FastAPI) -> None:
    while app.state.registry_syncer_running:
        try:
            _logger.debug("Syncing services between registry and database...")

            await _run_sync_services(app)

            await asyncio.sleep(app.state.settings.CATALOG_BACKGROUND_TASK_REST_TIME)

        except asyncio.CancelledError:
            # task is stopped
            _logger.info("registry syncing task cancelled")
            raise

        except Exception:  # pylint: disable=broad-except
            if not app.state.registry_syncer_running:
                _logger.warning("registry syncing task forced to stop")
                break
            _logger.exception("Unexpected error while syncing registry entries, restarting now...")
            # wait a bit before retrying, so it does not block everything until the director is up
            await asyncio.sleep(app.state.settings.CATALOG_BACKGROUND_TASK_WAIT_AFTER_FAILURE)


async def start_registry_sync_task(app: FastAPI) -> None:
    # FIXME: added this variable to overcome the state in which the
    # task cancelation is ignored and the exceptions enter in a loop
    # that never stops the background task. This flag is an additional
    # mechanism to enforce stopping the background task
    app.state.registry_syncer_running = True
    task = asyncio.create_task(_sync_services_task(app))
    app.state.registry_sync_task = task
    _logger.info("registry syncing task started")


async def stop_registry_sync_task(app: FastAPI) -> None:
    if task := app.state.registry_sync_task:
        with suppress(asyncio.CancelledError):
            app.state.registry_syncer_running = False
            task.cancel()
            await task
        app.state.registry_sync_task = None
    _logger.info("registry syncing task stopped")


async def background_task_lifespan(app: FastAPI) -> AsyncIterator[State]:
    await start_registry_sync_task(app)
    try:
        yield {}
    finally:
        await stop_registry_sync_task(app)
