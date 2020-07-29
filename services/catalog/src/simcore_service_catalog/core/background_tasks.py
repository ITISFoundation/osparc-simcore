import asyncio
import logging
from asyncio.futures import CancelledError
from os import sync
from typing import List

from aiopg.sa import Engine
from fastapi import Depends, FastAPI
from pydantic import ValidationError

from ..api.dependencies.database import get_repository
from ..api.dependencies.director import get_director_session
from ..db.repositories.services import ServicesRepository
from ..models.domain.service import ServiceAtDB, ServiceData
from ..services.director import AuthSession

logger = logging.getLogger(__name__)


async def _list_director_services(app: FastAPI) -> List[ServiceData]:
    client = get_director_session(app)
    data = await client.get("/services")
    services: List[ServiceData] = []
    for x in data:
        try:
            services.append(ServiceData.parse_obj(x))
        # services = parse_obj_as(List[ServiceOut], data)
        except ValidationError as exc:
            logger.warning(
                "skip service %s:%s that has invalid fields\n%s",
                x["key"],
                x["version"],
                exc,
            )

    return services


async def _list_db_services(app: FastAPI) -> List[ServiceAtDB]:
    engine: Engine = app.state.engine
    async with engine.acquire() as conn:
        services_repo = ServicesRepository(conn)
        return await services_repo.list_distinct_services()


async def sync_registry_task(app: FastAPI) -> None:
    # get list of services from director
    while True:
        try:
            await asyncio.sleep(5)
            logger.info("syncing...")
            services_in_registry = await _list_director_services(app)

            # logger.debug(
            #     "services in registry:\n%s",
            #     [
            #         f"{service.key}:{service.version}"
            #         for service in services_in_registry
            #     ],
            # )
            services_in_registry_filtered = [
                {service.key: service.version} for service in services_in_registry
            ]
            logger.debug("filtered registry:\n%s", services_in_registry_filtered)
            services_in_db = await _list_db_services(app)
            # logger.debug(
            #     "services in db:\n%s", services_in_db,
            # )
            services_in_db_filtered = [
                {service.key: service.version} for service in services_in_db
            ]
            logger.debug("filtered db:\n%s", services_in_db_filtered)
            # check that the db has all the services at least once
            # for service in services_in_db:

            # missing_services_in_db = []

        except CancelledError:
            return
        except Exception:
            logger.exception("some error occured")


async def start_registry_sync_task(app: FastAPI) -> None:
    task = asyncio.ensure_future(sync_registry_task(app))
    app.state.registry_sync_task = task


async def stop_registry_sync_task(app: FastAPI) -> None:
    task = app.state.registry_sync_task
    await task.cancel()
    await task.close()
