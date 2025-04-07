# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import httpx
from fastapi import status
from fastapi.testclient import TestClient
from pytest_mock import MockType


def test_sync_client(
    postgres_setup_disabled: MockType,
    rabbitmq_and_rpc_setup_disabled: None,
    background_tasks_setup_disabled: None,
    director_setup_disabled: None,
    client: TestClient,
):

    response = client.get("/v0/")
    assert response.status_code == status.HTTP_200_OK

    response = client.get("/v0/meta")
    assert response.status_code == status.HTTP_200_OK


async def test_async_client(
    postgres_setup_disabled: MockType,
    rabbitmq_and_rpc_setup_disabled: None,
    background_tasks_setup_disabled: None,
    director_setup_disabled: None,
    aclient: httpx.AsyncClient,
):
    response = await aclient.get("/v0/")
    assert response.status_code == status.HTTP_200_OK

    response = await aclient.get("/v0/meta")
    assert response.status_code == status.HTTP_200_OK
