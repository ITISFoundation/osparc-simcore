# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import unittest
from random import randint
from typing import Container, List

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from yarl import URL

from pytest_simcore.helpers.utils_mock import future_with_result
from simcore_service_catalog.api.dependencies.director import get_director_session
from simcore_service_catalog.api.routes import services
from simcore_service_catalog.models.domain.service import ServiceType
from simcore_service_catalog.models.schemas.service import ServiceOut

core_services = ["postgres"]
ops_services = ["adminer"]


@pytest.fixture(scope="session")
def fake_services() -> List[ServiceOut]:
    sleeper_service = ServiceOut(
        key="simcore/services/comp/itis/sleeper",
        version="15.2.4",
        type=ServiceType.computational,
        name="my service",
        description="a sleeping service",
        authors=[{"name": "me", "email": "me@myself.com"}],
        contact="me.myself@you.com",
        inputs=[],
        outputs=[],
    )
    return [sleeper_service.dict(by_alias=True)]


@pytest.fixture()
async def director_mockup(loop, monkeypatch, fake_services, app: FastAPI):
    async def return_list_services(user_id: int) -> List[ServiceOut]:
        return fake_services

    monkeypatch.setattr(services, "list_services", return_list_services)

    class FakeDirector:
        async def get(self, url: str):
            if url == "/services":
                return fake_services

    app.dependency_overrides[get_director_session] = FakeDirector


@pytest.fixture
def user_id() -> int:
    return randint(1, 10000)


async def test_director_mockup(
    director_mockup, app: FastAPI, fake_services: List[ServiceOut], user_id: int
):
    assert await services.list_services(user_id) == fake_services


def test_list_services(director_mockup, app: FastAPI, client: TestClient, user_id: int):
    url = URL("/v0/services").with_query(user_id=user_id)
    response = client.get(str(url))
    assert response.status_code == 200
