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
from asyncio.futures import CancelledError
from pprint import pformat
from typing import Dict, List, Optional, Set, Tuple

from aiopg.sa import Engine
from aiopg.sa.connection import SAConnection

from fastapi import FastAPI
from pydantic import ValidationError
from pydantic.types import PositiveInt
from simcore_service_catalog.db.repositories.projects import ProjectsRepository

from ..api.dependencies.director import get_director_session
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.services import ServicesRepository
from ..models.domain.service import (
    ServiceAccessRightsAtDB,
    ServiceDockerData,
    ServiceKeyVersion,
    ServiceMetaDataAtDB,
)

logger = logging.getLogger(__name__)

ServiceKey = str
ServiceVersion = str


async def _list_registry_services(
    app: FastAPI,
) -> Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData]:
    client = get_director_session(app)
    data = await client.get("/services")
    services: Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData] = {}
    for x in data:
        try:
            service_data = ServiceDockerData.parse_obj(x)
            services[(service_data.key, service_data.version)] = service_data
        # services = parse_obj_as(List[ServiceOut], data)
        except ValidationError as exc:
            logger.warning(
                "skip service %s:%s that has invalid fields\n%s",
                x["key"],
                x["version"],
                exc,
            )

    return services


async def _list_db_services(
    connection: SAConnection,
) -> Set[Tuple[ServiceKey, ServiceVersion]]:
    services_repo = ServicesRepository(connection)
    return {
        (service.key, service.version)
        for service in await services_repo.list_services()
    }


async def _get_service_access_rights(
    service: ServiceDockerData, connection: SAConnection
) -> Tuple[Optional[PositiveInt], List[ServiceAccessRightsAtDB]]:
    groups_repo = GroupsRepository(connection)
    everyone_gid = (await groups_repo.get_everyone_group()).gid
    owner_gid = None
    reader_gids: List[PositiveInt] = []
    # first get the owner emails
    possible_owner_email = [service.contact] + [
        author.email for author in service.authors
    ]

    for user_email in possible_owner_email:
        possible_gid = await groups_repo.get_user_gid_from_email(user_email)
        if possible_gid:
            reader_gids.append(possible_gid)
            if not owner_gid:
                owner_gid = possible_gid

    # there was no owner here, try with affiliation to some group
    possible_affiliations = [
        author.affiliation for author in service.authors if author.affiliation
    ]
    for user_affiliation in possible_affiliations:
        possible_gid = await groups_repo.get_gid_from_affiliation(user_affiliation)
        if possible_gid:
            reader_gids.append(possible_gid)
            if not owner_gid:
                owner_gid = possible_gid

    # if the service is part of a published template, it has to be available to everyone
    projects_repo = ProjectsRepository(connection)
    published_services: List[
        ServiceKeyVersion
    ] = await projects_repo.list_services_from_published_templates()
    if (
        ServiceKeyVersion(key=service.key, version=service.version)
        in published_services
    ):
        reader_gids.append(everyone_gid)

    # if no owner gid yet, we pass readable rights to the everyone group
    if not owner_gid:
        reader_gids.append(everyone_gid)

    # we add the owner with full rights, unless it's everyone
    access_rights = [
        ServiceAccessRightsAtDB(
            key=service.key,
            version=service.version,
            gid=gid,
            execute_access=True,
            write_access=(gid == owner_gid),
        )
        for gid in set(reader_gids)
    ]

    return (owner_gid, access_rights)


async def _create_services_in_db(
    connection: SAConnection,
    service_keys: Set[Tuple[ServiceKey, ServiceVersion]],
    services: Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData],
) -> None:

    services_repo = ServicesRepository(connection)
    for service_key, service_version in service_keys:
        service: ServiceDockerData = services[(service_key, service_version)]
        # find the service owner
        owner_gid, service_access_rights = await _get_service_access_rights(
            service, connection
        )
        # set the service in the DB
        await services_repo.create_service(
            ServiceMetaDataAtDB(**service.dict(), owner=owner_gid),
            service_access_rights,
        )


async def _ensure_registry_insync_with_db(
    app: FastAPI, connection: SAConnection
) -> None:
    services_in_registry: Dict[
        Tuple[ServiceKey, ServiceVersion], ServiceDockerData
    ] = await _list_registry_services(app)
    services_in_db: Set[Tuple[ServiceKey, ServiceVersion]] = await _list_db_services(
        connection
    )

    # check that the db has all the services at least once
    missing_services_in_db = set(services_in_registry.keys()) - services_in_db
    if missing_services_in_db:
        logger.debug(
            "missing services in db:\n%s", pformat(missing_services_in_db),
        )
        # update db (rationale: missing services are shared with everyone for now)
        await _create_services_in_db(
            connection, missing_services_in_db, services_in_registry
        )


async def _ensure_published_templates_accessible(connection: SAConnection) -> None:
    # Rationale: if a project template was published, its services must be available to everyone.
    # a published template has a column Published that is set to True
    projects_repo = ProjectsRepository(connection)
    published_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await projects_repo.list_services_from_published_templates()
    }

    groups_repo = GroupsRepository(connection)
    everyone_gid = (await groups_repo.get_everyone_group()).gid

    services_repo = ServicesRepository(connection)
    available_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await services_repo.list_services(
            gids=[everyone_gid], execute_access=True
        )
    }

    missing_services = published_services - available_services
    missing_services_access_rights = [
        ServiceAccessRightsAtDB(
            key=service[0], version=service[1], gid=everyone_gid, execute_access=True
        )
        for service in missing_services
    ]
    if missing_services_access_rights:
        logger.info(
            "Adding access rights for published templates\n: %s",
            missing_services_access_rights,
        )
        await services_repo.upsert_service_access_rights(missing_services_access_rights)


async def sync_registry_task(app: FastAPI) -> None:
    # get list of services from director
    engine: Engine = app.state.engine
    while True:
        try:
            async with engine.acquire() as conn:
                logger.debug("syncing services between registry and database...")
                # check that the list of services is in sync with the registry
                await _ensure_registry_insync_with_db(app, conn)

                # check that the published services are available to everyone (templates are published to GUESTs, so their services must be also accessible)
                await _ensure_published_templates_accessible(conn)

            await asyncio.sleep(app.state.settings.background_task_rest_time)

        except CancelledError:
            # task is stopped
            logger.debug("Catalog background task cancelled", exc_info=True)
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error while processing services entry")
            await asyncio.sleep(
                5
            )  # wait a bit before retrying, so it does not block everything until the director is up


async def start_registry_sync_task(app: FastAPI) -> None:
    task = asyncio.ensure_future(sync_registry_task(app))
    app.state.registry_sync_task = task


async def stop_registry_sync_task(app: FastAPI) -> None:
    task = app.state.registry_sync_task
    task.cancel()
    await task
