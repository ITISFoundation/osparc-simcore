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
from contextlib import suppress
from pprint import pformat
from typing import Any, Final, NewType, TypeAlias, cast

from fastapi import FastAPI
from models_library.function_services_catalog.api import iter_service_docker_data
from models_library.services import ServiceMetaDataPublished
from models_library.services_db import ServiceAccessRightsAtDB, ServiceMetaDataAtDB
from packaging.version import Version
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.dependencies.director import get_director_api
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.projects import ProjectsRepository
from ..db.repositories.services import ServicesRepository
from ..services import access_rights

_logger = logging.getLogger(__name__)

# NOTE: by PC I tried to unify with models_library.services but there are other inconsistencies so I leave if for another time!
ServiceKey = NewType("ServiceKey", str)
ServiceVersion = NewType("ServiceVersion", str)
ServiceDockerDataMap: TypeAlias = dict[
    tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished
]


async def _list_services_in_registry(
    app: FastAPI,
) -> ServiceDockerDataMap:
    client = get_director_api(app)
    registry_services = cast(list[dict[str, Any]], await client.get("/services"))

    services: ServiceDockerDataMap = {
        # services w/o associated image
        (s.key, s.version): s
        for s in iter_service_docker_data()
    }
    for service in registry_services:
        try:
            service_data = ServiceMetaDataPublished.parse_obj(service)
            services[(service_data.key, service_data.version)] = service_data

        except ValidationError:  # noqa: PERF203
            _logger.warning(
                "Skipping %s:%s from the catalog of services:",
                service.get("key"),
                service.get("version"),
                exc_info=True,
            )

    return services


async def _list_services_in_database(
    db_engine: AsyncEngine,
) -> set[tuple[ServiceKey, ServiceVersion]]:
    services_repo = ServicesRepository(db_engine=db_engine)
    return {
        (service.key, service.version)
        for service in await services_repo.list_services()
    }


async def _create_services_in_database(
    app: FastAPI,
    service_keys: set[tuple[ServiceKey, ServiceVersion]],
    services_in_registry: dict[
        tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished
    ],
) -> None:
    """Adds a new service in the database

    Determines the access rights of each service and adds it to the database
    """

    services_repo = ServicesRepository(app.state.engine)

    def _by_version(t: tuple[ServiceKey, ServiceVersion]) -> Version:
        return Version(t[1])

    sorted_services = sorted(service_keys, key=_by_version)

    for service_key, service_version in sorted_services:
        service_metadata: ServiceMetaDataPublished = services_in_registry[
            (service_key, service_version)
        ]
        ## Set deprecation date to null (is valid date value for postgres)

        # DEFAULT policies
        (
            owner_gid,
            service_access_rights,
        ) = await access_rights.evaluate_default_policy(app, service_metadata)

        # AUTO-UPGRADE PATCH policy
        inherited_access_rights = await access_rights.evaluate_auto_upgrade_policy(
            service_metadata, services_repo
        )

        service_access_rights += inherited_access_rights
        service_access_rights = access_rights.reduce_access_rights(
            service_access_rights
        )

        service_metadata_dict = service_metadata.dict()
        # set the service in the DB
        await services_repo.create_service(
            ServiceMetaDataAtDB(**service_metadata_dict, owner=owner_gid),
            service_access_rights,
        )


async def _ensure_registry_and_database_are_synced(app: FastAPI) -> None:
    """Ensures that the services listed in the database is in sync with the registry

    Notice that a services here refers to a 2-tuple (key, version)
    """
    services_in_registry: dict[
        tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished
    ] = await _list_services_in_registry(app)

    services_in_db: set[
        tuple[ServiceKey, ServiceVersion]
    ] = await _list_services_in_database(app.state.engine)

    # check that the db has all the services at least once
    missing_services_in_db = set(services_in_registry.keys()) - services_in_db
    if missing_services_in_db:
        _logger.debug(
            "Missing services in db: %s",
            pformat(missing_services_in_db),
        )

        # update db
        await _create_services_in_database(
            app, missing_services_in_db, services_in_registry
        )


async def _ensure_published_templates_accessible(
    db_engine: AsyncEngine, default_product_name: str
) -> None:
    # Rationale: if a project template was published, its services must be available to everyone.
    # a published template has a column Published that is set to True
    projects_repo = ProjectsRepository(db_engine)
    published_services: set[tuple[str, str]] = {
        (service.key, service.version)
        for service in await projects_repo.list_services_from_published_templates()
    }

    groups_repo = GroupsRepository(db_engine)
    everyone_gid = (await groups_repo.get_everyone_group()).gid

    services_repo = ServicesRepository(db_engine)
    available_services: set[tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[everyone_gid], execute_access=True
        )
    }

    missing_services = published_services - available_services
    missing_services_access_rights = [
        ServiceAccessRightsAtDB(
            key=service[0],
            version=service[1],
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


async def _sync_services_task(app: FastAPI) -> None:
    default_product: Final[str] = app.state.default_product_name
    engine: AsyncEngine = app.state.engine

    while app.state.registry_syncer_running:
        try:
            _logger.debug("Syncing services between registry and database...")

            # check that the list of services is in sync with the registry
            await _ensure_registry_and_database_are_synced(app)

            # check that the published services are available to everyone
            # (templates are published to GUESTs, so their services must be also accessible)
            await _ensure_published_templates_accessible(engine, default_product)

            await asyncio.sleep(app.state.settings.CATALOG_BACKGROUND_TASK_REST_TIME)

        except asyncio.CancelledError:  # noqa: PERF203
            # task is stopped
            _logger.info("registry syncing task cancelled")
            raise

        except Exception:  # pylint: disable=broad-except
            if not app.state.registry_syncer_running:
                _logger.warning("registry syncing task forced to stop")
                break
            _logger.exception(
                "Unexpected error while syncing registry entries, restarting now..."
            )
            # wait a bit before retrying, so it does not block everything until the director is up
            await asyncio.sleep(
                app.state.settings.CATALOG_BACKGROUND_TASK_WAIT_AFTER_FAILURE
            )


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
