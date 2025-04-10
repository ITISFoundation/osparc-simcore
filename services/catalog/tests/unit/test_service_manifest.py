# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
import toolz
from fastapi import FastAPI
from models_library.function_services_catalog.api import is_function_service
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api._dependencies.director import get_director_api
from simcore_service_catalog.clients.director import DirectorApi
from simcore_service_catalog.service import manifest


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


async def test_services_manifest_api(
    repository_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
):
    director_api = get_director_api(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorApi)

    # LIST
    all_services_map = await manifest.get_services_map(director_api)
    assert mocked_director_rest_api["list_services"].called

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
        service = await manifest.get_service(
            key=expected_service.key,
            version=expected_service.version,
            director_client=director_api,
        )

        assert service == expected_service
        if not is_function_service(service.key):
            assert mocked_director_rest_api["get_service"].called

    # BATCH
    for expected_services in toolz.partition(2, all_services_map.values()):
        selection = [(s.key, s.version) for s in expected_services]
        got_services = await manifest.get_batch_services(selection, director_api)

        assert [(s.key, s.version) for s in got_services] == selection

        # NOTE: simplier to visualize
        for got, expected in zip(got_services, expected_services, strict=True):
            assert got == expected
