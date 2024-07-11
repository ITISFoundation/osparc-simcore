# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import httpx
import pytest
import simcore_service_catalog.core.events
from fastapi import status
from pytest_mock import MockerFixture


@pytest.fixture
def spy_on_startup(mocker: MockerFixture):
    spy_startup = mocker.spy(
        simcore_service_catalog.core.events,
        "_flush_started_banner",
    )

    yield

    # if client/app fixtures are not initialized correctly, these events
    # might be called multiple times, which is wrong!
    assert spy_startup.call_count == 1


@pytest.fixture
def spy_on_shutdown(mocker: MockerFixture):
    spy_shutdown = mocker.spy(
        simcore_service_catalog.core.events,
        "_flush_finished_banner",
    )

    yield

    assert spy_shutdown.call_count == 1


def test_sync_client(
    spy_on_startup: None,
    postgres_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    background_tasks_setup_disabled: None,
    director_setup_disabled: None,
    client: httpx.Client,
    # spy_on_shutdown: None,
):

    response = client.get("/v0/")
    assert response.status_code == status.HTTP_200_OK

    response = client.get("/v0/meta")
    assert response.status_code == status.HTTP_200_OK


async def test_async_client(
    spy_on_startup: None,
    postgres_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    background_tasks_setup_disabled: None,
    director_setup_disabled: None,
    aclient: httpx.AsyncClient,
    # spy_on_shutdown: None,
):
    response = await aclient.get("/v0/")
    assert response.status_code == status.HTTP_200_OK

    response = await aclient.get("/v0/meta")
    assert response.status_code == status.HTTP_200_OK
