import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from pytest_mock import MockerFixture
from servicelib.fastapi.lifespan_utils import configure_app_lifespan
from simcore_service_api_server.services_http.rabbitmq import configure_rabbitmq


def test_configure_rabbitmq_disabled_uses_servicelib_only(mocker: MockerFixture):
    configure_rabbitmq_client = mocker.patch(
        "simcore_service_api_server.services_http.rabbitmq._configure_rabbitmq_client"
    )
    configure_rabbitmq_rpc_client = mocker.patch(
        "simcore_service_api_server.services_http.rabbitmq._configure_rabbitmq_rpc_client"
    )
    app_lifespan = mocker.Mock()

    configure_rabbitmq(app_lifespan, settings=None)

    configure_rabbitmq_client.assert_called_once_with(
        app_lifespan,
        settings=None,
        client_name="api_server",
        wait_for_connectivity=True,
    )
    configure_rabbitmq_rpc_client.assert_called_once_with(
        app_lifespan,
        settings=None,
        client_name="api_server_rpc_client",
        wait_for_connectivity=False,
    )
    app_lifespan.add.assert_not_called()


async def test_configure_rabbitmq_uses_servicelib_and_completes_component_teardown(
    mocker: MockerFixture,
):
    configure_rabbitmq_client = mocker.patch(
        "simcore_service_api_server.services_http.rabbitmq._configure_rabbitmq_client"
    )
    configure_rabbitmq_rpc_client = mocker.patch(
        "simcore_service_api_server.services_http.rabbitmq._configure_rabbitmq_rpc_client"
    )

    log_distributor = mocker.AsyncMock()
    health_checker = mocker.AsyncMock()
    health_checker.teardown.side_effect = RuntimeError("health checker teardown failed")
    mocker.patch(
        "simcore_service_api_server.services_http.rabbitmq.LogDistributor",
        return_value=log_distributor,
    )
    mocker.patch(
        "simcore_service_api_server.services_http.rabbitmq.ApiServerHealthChecker",
        return_value=health_checker,
    )
    mocker.patch("simcore_service_api_server.services_http.rabbitmq.resource_usage_tracker.setup")
    mocker.patch("simcore_service_api_server.services_http.rabbitmq.wb_api_server.setup")

    rabbitmq_settings = mocker.Mock()
    with configure_app_lifespan(started_banner="", starting_banner="") as app_lifespan:
        app = FastAPI(lifespan=app_lifespan)
        app.state.rabbitmq_client = mocker.Mock()
        app.state.rabbitmq_rpc_client = mocker.Mock()
        app.state.settings = mocker.Mock()
        configure_rabbitmq(app_lifespan, settings=rabbitmq_settings)

    configure_rabbitmq_client.assert_called_once_with(
        app_lifespan,
        settings=rabbitmq_settings,
        client_name="api_server",
        wait_for_connectivity=True,
    )
    configure_rabbitmq_rpc_client.assert_called_once_with(
        app_lifespan,
        settings=rabbitmq_settings,
        client_name="api_server_rpc_client",
        wait_for_connectivity=False,
    )

    with pytest.raises(RuntimeError, match="health checker teardown failed"):
        async with LifespanManager(app):
            pass

    health_checker.teardown.assert_awaited_once_with()
    log_distributor.teardown.assert_awaited_once_with()
