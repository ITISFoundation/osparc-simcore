# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access
# pylint:disable=not-an-iterable

import asyncio
from datetime import datetime
from random import randint
from typing import List, Optional

import pytest
from fastapi import FastAPI
from models_library.services import (
    ServiceAccessRightsAtDB,
    ServiceDockerData,
    ServiceType,
)
from pydantic.types import PositiveInt
from starlette.testclient import TestClient
from yarl import URL

import simcore_service_catalog.api.dependencies.director
from simcore_service_catalog.api.routes import services
from simcore_service_catalog.db.repositories.groups import GroupsRepository
from simcore_service_catalog.models.domain.group import GroupAtDB, GroupType
from simcore_service_catalog.models.schemas.services import ServiceOut

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
def registry_services() -> List[ServiceDockerData]:
    NUMBER_OF_SERVICES = 5
    return [
        ServiceDockerData(
            key="simcore/services/comp/my_comp_service",
            version=f"{v}.{randint(0,20)}.{randint(0,20)}",
            type=ServiceType.COMPUTATIONAL,
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
            key=s.key,
            version=s.version,
            gid=user_groups[0].gid,
            execute_access=True,
            product_name="osparc",
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
            if "/service_extras/" in url:
                return {
                    "build_date": f"{datetime.utcnow().isoformat(timespec='seconds')}Z"
                }

    def fake_director_api(*args, **kwargs):
        return FakeDirector()

    monkeypatch.setattr(
        simcore_service_catalog.api.dependencies.director,
        "get_director_api",
        fake_director_api,
    )

    # Check mock
    from simcore_service_catalog.api.dependencies.director import get_director_api

    assert isinstance(get_director_api(), FakeDirector)
    yield


@pytest.fixture()
async def db_mockup(
    loop,
    monkeypatch,
    app: FastAPI,
    user_groups: List[GroupAtDB],
    db_services: List[ServiceAccessRightsAtDB],
):
    async def return_list_user_groups(self, user_id: int) -> List[GroupAtDB]:
        return user_groups

    async def return_gid_from_email(*args, **kwargs) -> Optional[PositiveInt]:
        return user_groups[0].gid

    monkeypatch.setattr(GroupsRepository, "list_user_groups", return_list_user_groups)
    monkeypatch.setattr(
        GroupsRepository, "get_user_gid_from_email", return_gid_from_email
    )


async def test_director_mockup(
    director_mockup, app: FastAPI, registry_services: List[ServiceOut], user_id: int
):
    assert await services.list_services(user_id) == registry_services


@pytest.mark.skip(
    reason="Not ready, depency injection does not work, using monkeypatch. still issue with setting up database"
)
def test_list_services(
    director_mockup, db_mockup, app: FastAPI, client: TestClient, user_id: int
):
    asyncio.sleep(10)

    url = URL("/v0/services").with_query(user_id=user_id)
    response = client.get(str(url))
    assert response.status_code == 200
    data = response.json()
