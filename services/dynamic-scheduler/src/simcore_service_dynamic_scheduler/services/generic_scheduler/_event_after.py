import logging

from fastapi import FastAPI
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context

from ._core import start_operation
from ._models import (
    EventType,
    OperationContext,
    OperationName,
    ScheduleId,
)
from ._operation import OperationRegistry
from ._store import OperationEventsProxy, Store

_logger = logging.getLogger(__name__)


class AfterEventManager(SingletonInAppStateMixin):
    """
    Allows to register an operation to be started after
    another opearation ends the CREATED or UNDONE successfully.
    """

    app_state_name: str = "after_event_manager"

    def __init__(self, app: FastAPI) -> None:
        self.app = app
        self._store = Store.get_from_app_state(app)

    async def register_to_start_after(
        self,
        schedule_id: ScheduleId,
        event_type: EventType,
        *,
        operation_name: OperationName,
        initial_context: OperationContext,
    ) -> None:
        # ensure operation exists
        OperationRegistry.get_operation(operation_name)

        events_proxy = OperationEventsProxy(self._store, schedule_id, event_type)
        await events_proxy.create_or_update_multiple(
            {"initial_context": initial_context, "operation_name": operation_name}
        )

    async def safe_on_event_type(
        self, event_type: EventType, schedule_id: ScheduleId
    ) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            f"processing {event_type=} for {schedule_id=}",
            log_duration=True,
        ):
            await self._on_event_type(event_type, schedule_id)

    async def _on_event_type(
        self, event_type: EventType, schedule_id: ScheduleId
    ) -> None:
        events_proxy = OperationEventsProxy(self._store, schedule_id, event_type)

        # check if an entry exists for the operation
        if not await events_proxy.exists():
            # done processing remove item
            return

        operation_name = await events_proxy.read("operation_name")
        initial_context = await events_proxy.read("initial_context")
        new_schedule_id = await start_operation(
            self.app, operation_name, initial_context
        )

        await events_proxy.delete()

        _logger.debug(
            "Finished execution of event_type='%s' for schedule_id='%s'. "
            "Started new_schedule_id='%s' from operation_name='%s' with initial_context='%s'",
            event_type,
            schedule_id,
            new_schedule_id,
            operation_name,
            initial_context,
        )
