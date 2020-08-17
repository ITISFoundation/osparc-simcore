# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=not-an-iterable

from random import randint
from typing import List, Optional

import pytest
from fastapi import FastAPI
from simcore_service_catalog.api.dependencies.database import get_repository
from simcore_service_catalog.db.repositories.groups import GroupsRepository
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.models.domain.group import GroupAtDB, GroupType
from starlette.testclient import TestClient
from yarl import URL

from simcore_service_catalog.api.dependencies.director import get_director_session
from simcore_service_catalog.api.routes import services
from simcore_service_catalog.models.domain.service import (
    ServiceAccessRightsAtDB,
    ServiceType,
    ServiceOut,
)

core_services = ["postgres"]
ops_services = ["adminer"]


@pytest.fixture(scope="session")
def user_id() -> int:
    return randint(1, 10000)


@pytest.fixture(scope="session")
def user_groups(user_id: int) -> List[GroupAtDB]:
    return [
        GroupAtDB(
            gid=user_id,
            name="my primary group",
            description="it is primary",
            type=GroupType.PRIMARY,
        ),
        GroupAtDB(
            gid=randint(10001, 15000),
            name="all group",
            description="it is everyone",
            type=GroupType.EVERYONE,
        ),
        GroupAtDB(
            gid=randint(15001, 20000),
            name="standard group",
            description="it is standard",
            type=GroupType.STANDARD,
        ),
    ]


@pytest.fixture(scope="session")
def registry_services() -> List[ServiceOut]:
    NUMBER_OF_SERVICES = 5
    return [
        ServiceOut(
            key="simcore/services/comp/my_comp_service",
            version=f"{v}.{randint(0,20)}.{randint(0,20)}",
            type=ServiceType.computational,
            name=f"my service {v}",
            description="a sleeping service version {v}",
            authors=[{"name": "me", "email": "me@myself.com"}],
            contact="me.myself@you.com",
            inputs=[],
            outputs=[],
        )
        for v in range(NUMBER_OF_SERVICES)
    ]


@pytest.fixture(scope="session")
def db_services(
    registry_services: List[ServiceOut], user_groups: List[GroupAtDB]
) -> List[ServiceAccessRightsAtDB]:
    return [
        ServiceAccessRightsAtDB(
            key=s.key, tag=s.version, gid=user_groups[0].gid, execute_access=True
        )
        for s in registry_services
    ]


@pytest.fixture()
async def director_mockup(
    loop, monkeypatch, registry_services: List[ServiceOut], app: FastAPI
):
    async def return_list_services(user_id: int) -> List[ServiceOut]:
        return registry_services

    monkeypatch.setattr(services, "list_services", return_list_services)

    class FakeDirector:
        async def get(self, url: str):
            if url == "/services":
                return [s.dict(by_alias=True) for s in registry_services]

    app.dependency_overrides[get_director_session] = FakeDirector

    yield

    app.dependency_overrides[get_director_session] = None


@pytest.fixture()
async def db_mockup(
    loop,
    app: FastAPI,
    user_groups: List[GroupAtDB],
    db_services: List[ServiceAccessRightsAtDB],
):
    class FakeGroupsRepository:
        async def list_user_groups(self, user_id: int) -> List[GroupAtDB]:
            return user_groups

    app.dependency_overrides[get_repository(GroupsRepository)] = FakeGroupsRepository

    class FakeServicesRepository:
        async def list_services(
            self, gids: Optional[List[int]] = None
        ) -> List[ServiceAccessRightsAtDB]:
            return db_services

    app.dependency_overrides[
        get_repository(ServicesRepository)
    ] = FakeServicesRepository


async def test_director_mockup(
    director_mockup, app: FastAPI, registry_services: List[ServiceOut], user_id: int
):
    assert await services.list_services(user_id) == registry_services


@pytest.mark.skip(reason="Not ready, depency injection does not work")
def test_list_services(
    director_mockup, db_mockup, app: FastAPI, client: TestClient, user_id: int
):
    url = URL("/v0/services").with_query(user_id=user_id)
    response = client.get(str(url))
    assert response.status_code == 200
    data = response.json()
