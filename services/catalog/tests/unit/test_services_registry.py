# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from fastapi import FastAPI
from models_library.function_services_catalog.api import is_function_service
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.services.director import DirectorApi
from simcore_service_catalog.services.registry import (
    get_registered_service,
    get_registered_services_map,
)


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


async def test_registered_services(
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_api: MockRouter,
    app: FastAPI,
):
    director_api = get_director_api(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorApi)

    # LIST
    all_services_map = await get_registered_services_map(director_api)
    assert mocked_director_service_api["list_services"].called

    for service in all_services_map.values():
        if is_function_service(service.key):
            assert service.image_digest is None
        else:
            assert service.image_digest is not None

    services_image_digest = {
        s.image_digest for s in all_services_map.values() if s.image_digest
    }
    assert len(services_image_digest) < len(all_services_map)

    # GET
    for expected_service in all_services_map.values():
        service = await get_registered_service(
            expected_service.key, expected_service.version, director_api
        )

        assert service == expected_service
        if not is_function_service(service.key):
            assert mocked_director_service_api["get_service"].called
