import asyncio
import logging
from asyncio.futures import CancelledError
from pprint import pformat
from typing import Set, Tuple

from aiopg.sa import Engine
from fastapi import FastAPI
from pydantic import ValidationError

from ..api.dependencies.director import get_director_session
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.services import ServicesRepository
from ..models.domain.service import ServiceAccessRightsAtDB, ServiceData

logger = logging.getLogger(__name__)

ServiceKey = str
ServiceVersion = str


async def _list_registry_services(
    app: FastAPI,
) -> Set[Tuple[ServiceKey, ServiceVersion]]:
    client = get_director_session(app)
    data = await client.get("/services")
    services: Set[Tuple[ServiceKey, ServiceVersion]] = set()
    for x in data:
        try:
            service_data = ServiceData.parse_obj(x)
            services.add((service_data.key, service_data.version))
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
            for service in await services_repo.list_distinct_services()
        }


async def _get_everyone_gid(app: FastAPI) -> int:
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        groups_repo = GroupsRepository(conn)
        return (await groups_repo.get_everyone_group()).gid


async def _create_services_in_db(
    app: FastAPI, services: Set[Tuple[ServiceKey, ServiceVersion]]
) -> None:
    everyone_gid = await _get_everyone_gid(app)
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        services_repo = ServicesRepository(conn)
        for service_key, service_version in services:
            await services_repo.create_service(
                ServiceAccessRightsAtDB(
                    key=service_key,
                    tag=service_version,
                    gid=everyone_gid,
                    execute_access=True,
                )
            )


async def sync_registry_task(app: FastAPI) -> None:
    # get list of services from director
    while True:
        try:
            logger.debug("syncing services between registry and database...")
            services_in_registry: Set[
                Tuple[ServiceKey, ServiceVersion]
            ] = await _list_registry_services(app)

            services_in_db: Set[
                Tuple[ServiceKey, ServiceVersion]
            ] = await _list_db_services(app)

            # check that the db has all the services at least once

            missing_services_in_db = services_in_registry - services_in_db
            if missing_services_in_db:
                logger.debug(
                    "missing services in db:\n%s", pformat(missing_services_in_db),
                )
                # update db (rationale: missing services are shared with everyone for now)
                await _create_services_in_db(app, missing_services_in_db)

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
