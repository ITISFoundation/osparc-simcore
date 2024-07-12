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
    mocked_director_service_api: MockRouter,
    app: FastAPI,
):
    # gets director client as used in handlers
    director_api = get_director_api(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorApi)

    # PING
    assert await director_api.is_responsive()

    # LIST
    all_services = await director_api.list_all_services()
    assert mocked_director_service_api["list_services"].called

    services_image_digest = {service.image_digest for service in all_services}
    assert None not in services_image_digest
    assert len(services_image_digest) == len(all_services)

    # GET
    expected_service = all_services[0]
    assert (
        await director_api.get_service(expected_service.key, expected_service.version)
        == expected_service
    )


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

    service_extras = await director_api.get(
        f"/service_extras/{urllib.parse.quote_plus(key)}/{version}"
    )

    assert service_extras

    service = await director_api.get(
        f"/services/{urllib.parse.quote_plus(key)}/{version}"
    )
    assert service
