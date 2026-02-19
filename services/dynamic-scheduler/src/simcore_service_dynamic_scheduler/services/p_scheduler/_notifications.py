from functools import cached_property
from typing import Final

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ._fast_stream import FastStreamManager, MessageHandlerProtocol, RoutingKey
from ._models import StepId

RK_RECONSILIATION: Final[RoutingKey] = "reconciliation"
RK_STEP_CANCELLED: Final[RoutingKey] = "step.cancelled"
RK_STEP_READY: Final[RoutingKey] = "step.ready"


class NotificationsManager(SingletonInAppStateMixin):
    app_state_name: str = "p_scheduler_notifications_manager"

    def __init__(self, app: FastAPI) -> None:
        self.app = app

        self._handlers: dict[RoutingKey, MessageHandlerProtocol] = {}

    @cached_property
    def _fast_stream_manager(self) -> FastStreamManager:
        return FastStreamManager.get_from_app_state(self.app)

    def subscribe_handler(self, *, routing_key: RoutingKey, handler: MessageHandlerProtocol) -> None:
        self._handlers[routing_key] = handler

    def get_handlers(self) -> dict[RoutingKey, MessageHandlerProtocol]:
        return self._handlers

    async def send_riconciliation_event(self, node_id: NodeID) -> None:
        await self._fast_stream_manager.publish(node_id, routing_key=RK_RECONSILIATION)

    async def notify_step_cancelled(self, step_id: StepId) -> None:
        await self._fast_stream_manager.publish(step_id, routing_key=RK_STEP_CANCELLED)

    async def notify_step_ready(self, step_id: StepId) -> None:
        await self._fast_stream_manager.publish(step_id, routing_key=RK_STEP_READY)
