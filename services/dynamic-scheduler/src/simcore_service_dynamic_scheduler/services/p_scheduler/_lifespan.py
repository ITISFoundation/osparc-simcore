import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ...core.settings import ApplicationSettings, PScchedulerSettings
from ._fast_stream import FastStreamManager
from ._lifecycle_protocol import SupportsLifecycle
from ._metrics import MetricsManager
from ._node_status import StatusManager
from ._notifications import NotificationsManager
from ._reconciliation import ReconciliationManager
from ._worker import WorkerManager
from ._workflow_manager import WorkflowManager
from ._workflow_registry import WorkflowRegistry


async def p_scheduler_lifespan(app: FastAPI) -> AsyncIterator[State]:
    application_settings: ApplicationSettings = app.state.settings
    settings: PScchedulerSettings = application_settings.P_SCHEDULER

    workflow_manager = WorkflowManager(app)
    workflow_registry = WorkflowRegistry()

    reconciliaiton_manager = ReconciliationManager(
        app,
        periodic_checks_interval=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_RECONCILIATION_MANAGER_PERIODIC_CHECKS_INTERVAL,
        queue_consumer_expected_runtime_duration=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_RECONCILIATION_MANAGER_QUEUE_CONSUMER_EXPECTED_RUNTIME_DURATION,
        queue_max_burst=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_RECONCILIATION_MANAGER_QUEUE_MAX_BURST,
    )
    worker_manager = WorkerManager(
        app,
        check_for_steps_interval=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_WORKER_MANAGER_CHECK_FOR_STEPS_INTERVAL,
        heartbeat_interval=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_WORKER_MANAGER_HEARTBEAT_INTERVAL,
        queue_consumer_expected_runtime_duration=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_WORKER_MANAGER_QUEUE_CONSUMER_EXPECTED_RUNTIME_DURATION,
        queue_max_burst=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_WORKER_MANAGER_QUEUE_MAX_BURST,
    )

    status_manager = StatusManager(
        app,
        status_ttl=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_STATUS_MANAGER_STATUS_TTL,
        update_statuses_interval=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_STATUS_MANAGER_UPDATE_STATUSES_INTERVAL,
        max_parallel_updates=settings.DYNAMIC_SCHEDULER_P_SCCHEDULER_STATUS_MANAGER_MAX_PARALLEL_UPDATES,
    )

    notifications_manager = NotificationsManager(app)
    fast_stream_manager = FastStreamManager(
        application_settings.DYNAMIC_SCHEDULER_RABBITMQ,
        handlers=notifications_manager.get_handlers(),
        log_level=logging.INFO,
    )
    metrics_manager = MetricsManager(app)

    # lifecycle and state management

    setup_teardown: list[SupportsLifecycle] = [
        workflow_registry,
        reconciliaiton_manager,
        worker_manager,
        status_manager,
        fast_stream_manager,
    ]

    app_state_registration: list[SingletonInAppStateMixin] = [
        workflow_manager,
        workflow_registry,
        reconciliaiton_manager,
        worker_manager,
        status_manager,
        fast_stream_manager,
        notifications_manager,
        metrics_manager,
    ]

    for entry in app_state_registration:
        entry.set_to_app_state(app)

    for entry in setup_teardown:
        await entry.setup()

    yield {}

    for entry in setup_teardown:
        await entry.shutdown()

    for entry in app_state_registration:
        entry.pop_from_app_state(app)
