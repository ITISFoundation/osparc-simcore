# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import urllib.parse
from typing import Any

import pytest
from fastapi import FastAPI
from models_library.services_metadata_published import ServiceMetaDataPublished
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.services.director import DirectorApi


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch, app_environment: EnvVarsDict
) -> EnvVarsDict:
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "CATALOG_POSTGRES": "null",  # disable postgres
            "SC_BOOT_MODE": "local-development",
        },
    )


async def test_director_client_high_level_api(
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    expected_director_list_services: list[dict[str, Any]],
    mocked_director_service_api: MockRouter,
    app: FastAPI,
):
    # gets director client as used in handlers
    director_api = get_director_api(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorApi)

    # PING
    assert await director_api.is_responsive()

    # GET
    expected_service = ServiceMetaDataPublished(**expected_director_list_services[0])
    assert (
        await director_api.get_service(expected_service.key, expected_service.version)
        == expected_service
    )
    # TODO: error handling!


async def test_director_client_low_level_api(
    background_tasks_setup_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    expected_director_list_services: list[dict[str, Any]],
    app: FastAPI,
):
    director_api = get_director_api(app)

    expected_service = expected_director_list_services[0]
    key = expected_service["key"]
    version = expected_service["version"]

    service_labels = await director_api.get(
        f"/services/{urllib.parse.quote_plus(key)}/{version}/labels"
    )

    assert service_labels

    service = await director_api.get(
        f"/services/{urllib.parse.quote_plus(key)}/{version}"
    )
    assert service
