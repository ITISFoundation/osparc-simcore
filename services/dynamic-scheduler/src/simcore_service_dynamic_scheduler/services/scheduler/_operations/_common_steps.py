import logging

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ...generic_scheduler import (
    BaseStep,
    ProvidedOperationContext,
    RequiredOperationContext,
    ReservedContextKeys,
    ScheduleId,
)
from .._redis import RedisServiceStateManager

_logger = logging.getLogger(__name__)


class RegisterScheduleId(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {ReservedContextKeys.SCHEDULE_ID, "node_id"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        schedule_id: ScheduleId = required_context[ReservedContextKeys.SCHEDULE_ID]
        node_id: NodeID = required_context["node_id"]

        service_state_manager = RedisServiceStateManager(app=app, node_id=node_id)
        await service_state_manager.create_or_update("current_schedule_id", schedule_id)

        return None


class UnRegisterScheduleId(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        node_id: NodeID = required_context["node_id"]

        service_state_manager = RedisServiceStateManager(app=app, node_id=node_id)
        await service_state_manager.delete_key("current_schedule_id")

        return None


class DoNothing(BaseStep):
    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        _ = required_context
        _logger.debug("does nothing")

        return None
