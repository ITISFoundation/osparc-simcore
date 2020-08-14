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

from ..api.dependencies.director import get_director_session
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.services import ServicesRepository
from ..models.domain.service import (
    ServiceAccessRightsAtDB,
    ServiceDockerData,
    ServiceMetaDataAtDB,
)

"""This background task does the following:
1. gets the full list of services from the docker registry through the director
2. gets the same list from the DB
3. if services are missing from the DB, they are added with basic access rights
3.a. basic access rights are set as following:
    1. writable access allow the user to change meta data as well as access rights
    2. executable access allow the user to see/execute the service


"""


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


async def _list_db_services(app: FastAPI) -> Set[Tuple[ServiceKey, ServiceVersion]]:
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        services_repo = ServicesRepository(conn)
        return {
            (service.key, service.version)
            for service in await services_repo.list_services()
        }


async def _get_everyone_gid(app: FastAPI) -> int:
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        groups_repo = GroupsRepository(conn)
        return (await groups_repo.get_everyone_group()).gid


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
    app: FastAPI,
    service_keys: Set[Tuple[ServiceKey, ServiceVersion]],
    services: Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData],
) -> None:
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        services_repo = ServicesRepository(conn)
        for service_key, service_version in service_keys:
            service: ServiceDockerData = services[(service_key, service_version)]
            # find the service owner
            owner_gid, service_access_rights = await _get_service_access_rights(
                service, conn
            )
            # set the service in the DB
            await services_repo.create_service(
                ServiceMetaDataAtDB(**service.dict(), owner=owner_gid),
                service_access_rights,
            )


async def sync_registry_task(app: FastAPI) -> None:
    # get list of services from director
    while True:
        try:
            logger.debug("syncing services between registry and database...")
            services_in_registry: Dict[
                Tuple[ServiceKey, ServiceVersion], ServiceDockerData
            ] = await _list_registry_services(app)
            services_in_db: Set[
                Tuple[ServiceKey, ServiceVersion]
            ] = await _list_db_services(app)

            # check that the db has all the services at least once
            missing_services_in_db = set(services_in_registry.keys()) - services_in_db
            if missing_services_in_db:
                logger.debug(
                    "missing services in db:\n%s", pformat(missing_services_in_db),
                )
                # update db (rationale: missing services are shared with everyone for now)
                await _create_services_in_db(
                    app, missing_services_in_db, services_in_registry
                )

            await asyncio.sleep(app.state.settings.background_task_rest_time)

        except CancelledError:
            # task is stopped
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception("Error while processing services entry")
            await asyncio.sleep(5)  # wait a bit before retrying


async def start_registry_sync_task(app: FastAPI) -> None:
    task = asyncio.ensure_future(sync_registry_task(app))
    app.state.registry_sync_task = task


async def stop_registry_sync_task(app: FastAPI) -> None:
    task = app.state.registry_sync_task
    await task.cancel()
    await task.close()
