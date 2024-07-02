# pylint: disable=not-context-manager
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Iterator

import pytest
import respx
from fastapi import FastAPI
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from simcore_service_catalog.api.dependencies.director import get_director_api
from simcore_service_catalog.core.settings import ApplicationSettings
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


@pytest.fixture
def mocked_director_service_api(
    app_settings: ApplicationSettings,
) -> Iterator[MockRouter]:
    assert app_settings.CATALOG_DIRECTOR
    with respx.mock(
        base_url=app_settings.CATALOG_DIRECTOR.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.head("/", name="healthcheck").respond(200, json={"health": "OK"})
        respx_mock.get("/services", name="list_services").respond(
            200, json={"data": ["one", "two"]}
        )

        yield respx_mock


async def test_director_client_setup(
    mocked_director_service_api: MockRouter,
    app: FastAPI,
):
    # gets director client as used in handlers
    director_api = get_director_api(app)

    assert app.state.director_api == director_api
    assert isinstance(director_api, DirectorApi)

    # use it
    data = await director_api.get("/services")

    # director entry-point has hit
    assert mocked_director_service_api["list_services"].called

    # returns un-enveloped response
    assert data == ["one", "two"]
