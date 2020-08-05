import asyncio
import logging
from asyncio.futures import CancelledError
from pprint import pformat
from typing import Dict, Set, Tuple

from aiopg.sa import Engine
from fastapi import FastAPI
from pydantic import ValidationError

from ..api.dependencies.director import get_director_session
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.services import ServicesRepository
from ..models.domain.service import (
    ServiceAccessRightsAtDB,
    ServiceDockerData,
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


async def _create_services_in_db(
    app: FastAPI,
    service_keys: Set[Tuple[ServiceKey, ServiceVersion]],
    services: Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData],
) -> None:
    everyone_gid = await _get_everyone_gid(app)
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        services_repo = ServicesRepository(conn)
        for service_key, service_version in service_keys:
            service: ServiceDockerData = services[(service_key, service_version)]
            await services_repo.create_service(
                ServiceMetaDataAtDB.parse_obj(service),
                ServiceAccessRightsAtDB(
                    key=service_key,
                    version=service_version,
                    gid=everyone_gid,
                    execute_access=True,
                ),
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

            await asyncio.sleep(5)

        except CancelledError:
            # task is stopped
            return
        except Exception:  # pylint: disable=broad-except
            logger.exception("some error occured")


async def start_registry_sync_task(app: FastAPI) -> None:
    task = asyncio.ensure_future(sync_registry_task(app))
    app.state.registry_sync_task = task


async def stop_registry_sync_task(app: FastAPI) -> None:
    task = app.state.registry_sync_task
    await task.cancel()
    await task.close()
