import logging

from fastapi import FastAPI
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context

from ._core import start_operation
from ._errors import OperationInitialContextKeyNotFoundError
from ._models import (
    EventType,
    OperationContext,
    OperationName,
    OperationToStart,
    ScheduleId,
)
from ._operation import OperationRegistry
from ._store import OperationEventsProxy, Store

_logger = logging.getLogger(__name__)


class AfterEventManager(SingletonInAppStateMixin):
    """
    Allows to register an operation to be started after
    another operation ends the EXECUTED or REVERTED successfully.
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
        to_start: OperationToStart | None,
    ) -> None:
        events_proxy = OperationEventsProxy(self._store, schedule_id, event_type)
        if to_start is None:
            # unregister any previously registered operation
            await events_proxy.delete()
            _logger.debug(
                "Unregistered event_type='%s' to_start for schedule_id='%s'",
                event_type,
                schedule_id,
            )
            return

        # ensure operation exists
        operation = OperationRegistry.get_operation(to_start.operation_name)
        for required_key in operation.initial_context_required_keys:
            if required_key not in to_start.initial_context:
                raise OperationInitialContextKeyNotFoundError(
                    operation_name=to_start.operation_name, required_key=required_key
                )

        await events_proxy.create_or_update_multiple(
            {
                "initial_context": to_start.initial_context,
                "operation_name": to_start.operation_name,
            }
        )
        _logger.debug(
            "Registered event_type='%s' to_start='%s' for schedule_id='%s'",
            event_type,
            to_start,
            schedule_id,
        )

    async def safe_on_event_type(
        self,
        event_type: EventType,
        schedule_id: ScheduleId,
        operation_name: OperationName,
        initial_context: OperationContext,
    ) -> None:
        with log_context(
            _logger,
            logging.DEBUG,
            f"processing {event_type=} for {schedule_id=} {operation_name=} {initial_context=}",
            log_duration=True,
        ):
            new_schedule_id = await start_operation(
                self.app, operation_name, initial_context
            )
            _logger.debug(
                "Finished execution of event_type='%s' for schedule_id='%s'. "
                "Started new_schedule_id='%s' from operation_name='%s' with initial_context='%s'",
                event_type,
                schedule_id,
                new_schedule_id,
                operation_name,
                initial_context,
            )
