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
from datetime import datetime
from pprint import pformat
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import quote_plus

from aiopg.sa import Engine
from fastapi import FastAPI
from models_library.services import (
    ServiceAccessRightsAtDB,
    ServiceDockerData,
    ServiceMetaDataAtDB,
)
from pydantic import ValidationError
from pydantic.types import PositiveInt

from ..api.dependencies.director import get_director_api
from ..db.repositories.groups import GroupsRepository
from ..db.repositories.projects import ProjectsRepository
from ..db.repositories.services import ServicesRepository
from ..services.frontend_services import iter_service_docker_data

logger = logging.getLogger(__name__)

ServiceKey = str
ServiceVersion = str

OLD_SERVICES_DATE: datetime = datetime(2020, 8, 19)

ServiceDockerDataMap = Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData]


async def _list_registry_services(
    app: FastAPI,
) -> ServiceDockerDataMap:
    client = get_director_api(app)
    data = await client.get("/services")
    services: ServiceDockerDataMap = {
        (s.key, s.version): s for s in iter_service_docker_data()
    }
    for x in data:
        try:
            service_data = ServiceDockerData.parse_obj(x)
            services[(service_data.key, service_data.version)] = service_data
        # services = parse_obj_as(List[ServiceDockerData], data)
        except ValidationError as exc:
            logger.warning(
                "skip service %s:%s that has invalid fields\n%s",
                x.get("key"),
                x.get("version"),
                exc,
            )

    return services


async def _list_db_services(
    db_engine: Engine,
) -> Set[Tuple[ServiceKey, ServiceVersion]]:
    services_repo = ServicesRepository(db_engine=db_engine)
    return {
        (service.key, service.version)
        for service in await services_repo.list_services()
    }


async def _create_service_default_access_rights(
    app: FastAPI, service: ServiceDockerData, db_engine: Engine
) -> Tuple[Optional[PositiveInt], List[ServiceAccessRightsAtDB]]:
    """Rationale as of 19.08.2020: all services that were put in oSparc before today
    will be visible to everyone.
    The services afterwards will be visible ONLY to his/her owner.
    """

    async def _is_old_service(app: FastAPI, service: ServiceDockerData) -> bool:
        # get service build date
        client = get_director_api(app)
        data = await client.get(
            f"/service_extras/{quote_plus(service.key)}/{service.version}"
        )
        if not data or "build_date" not in data:
            return True

        logger.debug("retrieved service extras are %s", data)

        service_build_data = datetime.strptime(data["build_date"], "%Y-%m-%dT%H:%M:%SZ")
        return service_build_data < OLD_SERVICES_DATE

    groups_repo = GroupsRepository(db_engine)
    everyone_gid = (await groups_repo.get_everyone_group()).gid
    owner_gid = None
    reader_gids: List[PositiveInt] = []

    def _is_frontend_service(service: ServiceDockerData) -> bool:
        return "/frontend/" in service.key

    if _is_frontend_service(service) or await _is_old_service(app, service):
        logger.debug("service %s:%s is old or frontend", service.key, service.version)
        # let's make that one available to everyone
        reader_gids.append(everyone_gid)

    # try to find the owner
    possible_owner_email = [service.contact] + [
        author.email for author in service.authors
    ]

    for user_email in possible_owner_email:
        possible_gid = await groups_repo.get_user_gid_from_email(user_email)
        if possible_gid:
            if not owner_gid:
                owner_gid = possible_gid
    if not owner_gid:
        logger.warning("service %s:%s has no owner", service.key, service.version)
    else:
        reader_gids.append(owner_gid)

    # we add the owner with full rights, unless it's everyone
    access_rights = [
        ServiceAccessRightsAtDB(
            key=service.key,
            version=service.version,
            gid=gid,
            execute_access=True,
            write_access=(gid == owner_gid),
            product_name=app.state.settings.access_rights_default_product_name,
        )
        for gid in set(reader_gids)
    ]

    return (owner_gid, access_rights)


async def _create_services_in_db(
    app: FastAPI,
    db_engine: Engine,
    service_keys: Set[Tuple[ServiceKey, ServiceVersion]],
    services: Dict[Tuple[ServiceKey, ServiceVersion], ServiceDockerData],
) -> None:

    services_repo = ServicesRepository(db_engine)
    for service_key, service_version in service_keys:
        service: ServiceDockerData = services[(service_key, service_version)]
        # find the service owner
        owner_gid, service_access_rights = await _create_service_default_access_rights(
            app, service, db_engine
        )
        # set the service in the DB
        await services_repo.create_service(
            ServiceMetaDataAtDB(**service.dict(), owner=owner_gid),
            service_access_rights,
        )


async def _ensure_registry_insync_with_db(app: FastAPI, db_engine: Engine) -> None:
    services_in_registry: Dict[
        Tuple[ServiceKey, ServiceVersion], ServiceDockerData
    ] = await _list_registry_services(app)
    services_in_db: Set[Tuple[ServiceKey, ServiceVersion]] = await _list_db_services(
        db_engine
    )

    # check that the db has all the services at least once
    missing_services_in_db = set(services_in_registry.keys()) - services_in_db
    if missing_services_in_db:
        logger.debug(
            "missing services in db:\n%s",
            pformat(missing_services_in_db),
        )
        # update db (rationale: missing services are shared with everyone for now)
        await _create_services_in_db(
            app, db_engine, missing_services_in_db, services_in_registry
        )


async def _ensure_published_templates_accessible(
    db_engine: Engine, default_product_name: str
) -> None:
    # Rationale: if a project template was published, its services must be available to everyone.
    # a published template has a column Published that is set to True
    projects_repo = ProjectsRepository(db_engine)
    published_services: Set[Tuple[str, str]] = {
        (service.key, service.version)
        for service in await projects_repo.list_services_from_published_templates()
    }

    groups_repo = GroupsRepository(db_engine)
    everyone_gid = (await groups_repo.get_everyone_group()).gid

    services_repo = ServicesRepository(db_engine)
    available_services: Set[Tuple[str, str]] = {
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
        logger.info(
            "Adding access rights for published templates\n: %s",
            missing_services_access_rights,
        )
        await services_repo.upsert_service_access_rights(missing_services_access_rights)


async def sync_registry_task(app: FastAPI) -> None:
    # get list of services from director
    default_product: str = app.state.settings.access_rights_default_product_name
    engine: Engine = app.state.engine

    while True:
        try:
            logger.debug("syncing services between registry and database...")

            # check that the list of services is in sync with the registry
            await _ensure_registry_insync_with_db(app, engine)

            # check that the published services are available to everyone
            # (templates are published to GUESTs, so their services must be also accessible)
            await _ensure_published_templates_accessible(engine, default_product)

            await asyncio.sleep(app.state.settings.background_task_rest_time)

        except CancelledError:
            # task is stopped
            logger.debug("Catalog background task cancelled", exc_info=True)
            return

        except Exception:  # pylint: disable=broad-except
            logger.exception("Error while processing services entry")
            # wait a bit before retrying, so it does not block everything until the director is up
            await asyncio.sleep(app.state.settings.background_task_wait_after_failure)


async def start_registry_sync_task(app: FastAPI) -> None:
    task = asyncio.ensure_future(sync_registry_task(app))
    app.state.registry_sync_task = task


async def stop_registry_sync_task(app: FastAPI) -> None:
    task = app.state.registry_sync_task
    task.cancel()
    await task
