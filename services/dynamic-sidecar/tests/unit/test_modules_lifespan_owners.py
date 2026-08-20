from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pytest_mock import MockerFixture
from simcore_service_dynamic_sidecar.modules.file_notification_subscriber import (
    configure_file_notification_subscriber,
)
from simcore_service_dynamic_sidecar.modules.prometheus_metrics import configure_prometheus_metrics
from simcore_service_dynamic_sidecar.modules.resource_tracking import configure_resource_tracking
from simcore_service_dynamic_sidecar.modules.system_monitor import configure_system_monitor
from simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage import configure_disk_usage
from simcore_service_dynamic_sidecar.modules.user_services_preferences import (
    configure_user_services_preferences,
)


async def test_configure_file_notification_subscriber_lifespan() -> None:
    app = FastAPI()
    app.state.settings = Mock(DY_SIDECAR_NODE_ID="node", DY_SIDECAR_PROJECT_ID="project")
    app.state.rabbitmq_client = rabbitmq_client = AsyncMock()
    rabbitmq_client.subscribe.return_value = ("queue", "consumer-tag")
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_file_notification_subscriber(app_lifespan)

    async with app_lifespan(app):
        assert app.state.file_notification_state.queue_name == "queue"

    rabbitmq_client.unsubscribe.assert_awaited_once_with("queue")


async def test_configure_prometheus_metrics_lifespan(mocker: MockerFixture) -> None:
    app = FastAPI()
    metrics_command = Mock()
    app.state.settings = Mock(DY_SIDECAR_CALLBACKS_MAPPING=Mock(metrics=metrics_command))
    app.state.shared_store = Mock()
    user_service_metrics = AsyncMock()
    user_service_metrics_class = mocker.patch(
        "simcore_service_dynamic_sidecar.modules.prometheus_metrics.UserServicesMetrics",
        return_value=user_service_metrics,
    )
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_prometheus_metrics(app_lifespan)

    async with app_lifespan(app):
        user_service_metrics.start.assert_awaited_once_with()

    user_service_metrics_class.assert_called_once_with(app.state.shared_store, metrics_command)
    user_service_metrics.stop.assert_awaited_once_with()


async def test_configure_resource_tracking_lifespan(mocker: MockerFixture) -> None:
    app = FastAPI()
    stop_heart_beat_task = mocker.patch(
        "simcore_service_dynamic_sidecar.modules.resource_tracking._setup.stop_heart_beat_task",
        autospec=True,
    )
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_resource_tracking(app_lifespan)

    async with app_lifespan(app):
        assert app.state.resource_tracking is not None

    stop_heart_beat_task.assert_awaited_once_with(app)


async def test_configure_disk_usage_lifespan(mocker: MockerFixture) -> None:
    app = FastAPI()
    disk_usage_monitor = AsyncMock()
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.system_monitor._disk_usage.create_disk_usage_monitor",
        return_value=disk_usage_monitor,
    )
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_disk_usage(app_lifespan)

    async with app_lifespan(app):
        disk_usage_monitor.setup.assert_awaited_once_with()

    disk_usage_monitor.shutdown.assert_awaited_once_with()


async def test_configure_system_monitor_disabled(mocker: MockerFixture) -> None:
    app = FastAPI()
    app.state.settings = Mock(SYSTEM_MONITOR_SETTINGS=Mock(DY_SIDECAR_SYSTEM_MONITOR_TELEMETRY_ENABLE=False))
    configure_disk_usage_mock = mocker.patch(
        "simcore_service_dynamic_sidecar.modules.system_monitor._setup.configure_disk_usage"
    )
    display_current_disk_usage = mocker.patch(
        "simcore_service_dynamic_sidecar.modules.system_monitor._setup._display_current_disk_usage",
        autospec=True,
    )
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_system_monitor(app, app_lifespan)

    async with app_lifespan(app):
        pass

    configure_disk_usage_mock.assert_not_called()
    display_current_disk_usage.assert_awaited_once_with(app)


async def test_configure_user_services_preferences_disabled(mocker: MockerFixture) -> None:
    app = FastAPI()
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.user_services_preferences._setup.is_feature_enabled",
        return_value=False,
    )
    app_lifespan: LifespanManager[FastAPI] = LifespanManager()
    configure_user_services_preferences(app_lifespan)

    async with app_lifespan(app):
        assert not hasattr(app.state, "user_services_preferences_manager")
