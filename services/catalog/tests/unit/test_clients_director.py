# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import urllib.parse
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, status
from models_library.services_metadata_published import ServiceMetaDataPublished
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api._dependencies.director import get_director_client
from simcore_service_catalog.clients.director import DirectorClient


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "SC_BOOT_MODE": "local-development",
        },
    )


@pytest.fixture
def service_key_and_version(
    expected_director_rest_api_list_services: list[dict[str, Any]],
) -> tuple[str, str]:
    expected_service = expected_director_rest_api_list_services[0]
    return expected_service["key"], expected_service["version"]


async def test_director_client_high_level_api(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    expected_director_rest_api_list_services: list[dict[str, Any]],
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
):
    # gets director client as used in handlers
    director_api = get_director_client(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorClient)

    # PING
    assert await director_api.is_responsive()

    # GET
    expected_service = ServiceMetaDataPublished(
        **expected_director_rest_api_list_services[0]
    )
    assert (
        await director_api.get_service(expected_service.key, expected_service.version)
        == expected_service
    )


async def test_director_client_low_level_api(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
):
    director_api = get_director_client(app)

    key, version = service_key_and_version

    service_labels = await director_api.get(
        f"/services/{urllib.parse.quote_plus(key)}/{version}/labels"
    )

    assert service_labels

    service = await director_api.get(
        f"/services/{urllib.parse.quote_plus(key)}/{version}"
    )
    assert service


async def test_director_client_get_service_extras_with_org_labels(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    service_key_and_version: tuple[str, str],
    app: FastAPI,
):
    director_api = get_director_client(app)

    key, version = service_key_and_version

    service_extras = await director_api.get_service_extras(key, version)

    # Check node requirements are present
    assert service_extras.node_requirements is not None
    assert service_extras.node_requirements.cpu > 0
    assert service_extras.node_requirements.ram > 0

    # Check service build details are present (since we have org.label-schema labels)
    assert service_extras.service_build_details is not None
    assert service_extras.service_build_details.build_date == "2023-04-17T08:04:15Z"
    assert (
        service_extras.service_build_details.vcs_ref
        == "4d79449a2e79f8a3b3b2e1dd0290af9f3d1a8792"
    )
    assert (
        service_extras.service_build_details.vcs_url
        == "https://github.com/ITISFoundation/jupyter-math.git"
    )


async def test_director_client_get_service_extras_without_org_labels(
    repository_lifespan_disabled: None,
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api_base: MockRouter,
    service_key_and_version: tuple[str, str],
    get_mocked_service_labels: Callable[[str, str, bool], dict],
    app: FastAPI,
):
    # Setup mock without org.label-schema labels
    service_key, service_version = service_key_and_version

    # Mock the labels endpoint without org labels
    @mocked_director_rest_api_base.get(
        path__regex=r"^/services/(?P<service_key>[/\w-]+)/(?P<service_version>[0-9\.]+)/labels$",
        name="get_service_labels_no_org",
    )
    def _get_service_labels_no_org(request, service_key, service_version):
        return httpx.Response(
            status_code=status.HTTP_200_OK,
            json={
                "data": get_mocked_service_labels(
                    service_key, service_version, include_org_labels=False
                )
            },
        )

    director_api = get_director_client(app)
    service_extras = await director_api.get_service_extras(service_key, service_version)

    # Check node requirements are present
    assert service_extras.node_requirements is not None
    assert service_extras.node_requirements.cpu > 0
    assert service_extras.node_requirements.ram > 0

    # Check service build details are NOT present (since we don't have org.label-schema labels)
    assert service_extras.service_build_details is None
