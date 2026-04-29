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
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import suppress
from pprint import pformat
from typing import Final

from fastapi import FastAPI, HTTPException
from fastapi_lifespan_manager import State
from models_library.services import ServiceMetaDataPublished
from models_library.services_types import ServiceKey, ServiceVersion
from packaging.version import Version
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api._dependencies.director import get_director_client
from ..models.services_db import ServiceAccessRightsDB, ServiceMetaDataDBCreate
from ..repository.groups import GroupsRepository
from ..repository.projects import ProjectsRepository
from ..repository.services import ServicesRepository
from ..service import access_rights, manifest

_logger = logging.getLogger(__name__)


async def _list_services_in_database(
    db_engine: AsyncEngine,
):
    services_repo = ServicesRepository(db_engine=db_engine)
    return {(service.key, service.version) for service in await services_repo.list_services()}


async def _create_services_in_database(
    app: FastAPI,
    service_keys: set[tuple[ServiceKey, ServiceVersion]],
    services_in_registry: dict[tuple[ServiceKey, ServiceVersion], ServiceMetaDataPublished],
) -> None:
    """Adds a new service in the database

    Determines the access rights of each service and adds it to the database
    """

    services_repo = ServicesRepository(app.state.engine)

    def _by_version(t: tuple[ServiceKey, ServiceVersion]) -> Version:
        return Version(t[1])

    sorted_services = sorted(service_keys, key=_by_version)

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

        except (HTTPException, ValidationError, SQLAlchemyError) as err:
            # Resilient to single failures: errors in individual (service,key) should not prevent the evaluation of the rest
            # and stop the background task from running.
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/6318
            _logger.warning(
                "Skipping '%s:%s' due to %s",
                service_key,
                service_version,
                err,
            )


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

        # update db
        await _create_services_in_database(app, missing_services_in_db, services_in_manifest_map)


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


async def _ensure_access_rights_propagated(db_engine: AsyncEngine) -> None:
    """Self-healing: propagates access rights forward through patch version chains.

    For each service key, groups versions by major.minor and checks consecutive
    patch versions. If a newer patch version is missing access rights that its
    predecessor has, the missing rights are copied via upsert.

    This repairs incomplete inheritance caused by race conditions between
    multiple catalog replicas, transient director API failures, or any other
    situation where the initial sync created metadata but failed to inherit
    the full set of access rights.
    """
    services_repo = ServicesRepository(db_engine)
    all_services = await services_repo.list_services()

    # Group by service key
    services_by_key: dict[str, list[tuple[Version, str]]] = defaultdict(list)
    for svc in all_services:
        try:
            services_by_key[svc.key].append((Version(svc.version), svc.version))
        except Exception:  # pylint: disable=broad-except
            _logger.debug("Skipping service with invalid version %s:%s", svc.key, svc.version)
            continue

    for service_key, version_tuples in services_by_key.items():
        sorted_versions = sorted(version_tuples, key=lambda t: t[0])

        # Group by (major, minor)
        by_major_minor: dict[tuple[int, int], list[str]] = defaultdict(list)
        for parsed, raw in sorted_versions:
            by_major_minor[(parsed.major, parsed.minor)].append(raw)

        for patch_versions in by_major_minor.values():
            if len(patch_versions) < 2:
                continue

            prev_version = patch_versions[0]
            prev_rights = await services_repo.get_service_access_rights(service_key, prev_version)

            for curr_version in patch_versions[1:]:
                curr_rights = await services_repo.get_service_access_rights(service_key, curr_version)

                prev_set = {(r.gid, r.product_name) for r in prev_rights}
                curr_set = {(r.gid, r.product_name) for r in curr_rights}
                missing = prev_set - curr_set

                if missing:
                    prev_rights_map = {(r.gid, r.product_name): r for r in prev_rights}
                    rights_to_add = [
                        ServiceAccessRightsDB(
                            key=ServiceKey(service_key),
                            version=ServiceVersion(curr_version),
                            gid=prev_rights_map[key].gid,
                            product_name=prev_rights_map[key].product_name,
                            execute_access=prev_rights_map[key].execute_access,
                            write_access=prev_rights_map[key].write_access,
                        )
                        for key in missing
                    ]
                    _logger.warning(
                        "Repairing %d missing access rights for %s:%s (inherited from %s). Missing: %s",
                        len(rights_to_add),
                        service_key,
                        curr_version,
                        prev_version,
                        missing,
                    )
                    await services_repo.upsert_service_access_rights(rights_to_add)

                    # Refresh current rights after repair for the next iteration
                    curr_rights = await services_repo.get_service_access_rights(service_key, curr_version)

                prev_version = curr_version
                prev_rights = curr_rights


async def _run_sync_services(app: FastAPI):
    default_product: Final[str] = app.state.default_product_name
    engine: AsyncEngine = app.state.engine

    # check that the list of services is in sync with the registry
    await _ensure_registry_and_database_are_synced(app)

    # self-heal: propagate access rights forward through patch versions
    await _ensure_access_rights_propagated(engine)

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
