# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from dataclasses import dataclass

import pytest
import respx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture
from servicelib.fastapi.lifespan_utils import configure_app_lifespan
from simcore_service_api_server.utils.client_base import (
    BaseServiceClientApi,
    configure_client_instance,
)


@pytest.fixture
def the_service():
    # pylint: disable=not-context-manager
    with respx.mock(
        base_url="http://the_service",
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.get("/health", name="health_check").respond(200, content="healthy")

        yield respx_mock


async def test_configure_client_instance(the_service):
    @dataclass
    class TheClientApi(BaseServiceClientApi):
        x: int = 33

    # setup app
    with configure_app_lifespan(started_banner="", starting_banner="") as app_lifespan:
        app = FastAPI(lifespan=app_lifespan)
        assert not TheClientApi.get_instance(app)

        configure_client_instance(
            app,
            app_lifespan,
            api_cls=TheClientApi,
            api_baseurl="http://the_service",
            service_name="the_service",
            health_check_path="/health",
            x=42,
            tracing_settings=None,
        )
    assert not TheClientApi.get_instance(app)

    # test startup/shutdown
    async with LifespanManager(app):
        # check startup
        assert TheClientApi.get_instance(app)
        api_obj = TheClientApi.get_instance(app)

        assert await api_obj.is_responsive()
        assert the_service["health_check"].called

    # check shutdown
    assert not TheClientApi.get_instance(app), "Expected automatically cleaned"
    # assert not await api_obj.is_responsive(), "Expected already closed"

    assert the_service["health_check"].call_count == 1


async def test_configure_client_instance_closes_client_when_tracing_setup_raises(
    mocker: MockerFixture,
):
    @dataclass
    class TheClientApi(BaseServiceClientApi):
        pass

    client = mocker.AsyncMock()
    mocker.patch(
        "simcore_service_api_server.utils.client_base.AsyncClient",
        return_value=client,
    )
    mocker.patch("simcore_service_api_server.utils.client_base.get_tracing_config")
    mocker.patch(
        "simcore_service_api_server.utils.client_base.setup_httpx_client_tracing",
        side_effect=RuntimeError("tracing setup failed"),
    )

    with configure_app_lifespan(started_banner="", starting_banner="") as app_lifespan:
        app = FastAPI(lifespan=app_lifespan)
        configure_client_instance(
            app,
            app_lifespan,
            api_cls=TheClientApi,
            api_baseurl="http://the_service",
            service_name="the_service",
            tracing_settings=mocker.Mock(),
        )

    with pytest.raises(RuntimeError, match="tracing setup failed"):
        async with LifespanManager(app):
            pytest.fail("app startup should have failed before entering the context")

    client.aclose.assert_awaited_once_with()
