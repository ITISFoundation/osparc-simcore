from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from simcore_service_dynamic_scheduler.services.generic_scheduler._core import (
    ScheduleId,
)

from ...generic_scheduler import (
    BaseStep,
    ProvidedOperationContext,
    RequiredOperationContext,
    ReservedContextKeys,
)
from .._redis import RedisServiceStateManager


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
