import logging

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ...generic_scheduler import (
    BaseStep,
    Operation,
    OperationToStart,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
    start_operation,
)
from .. import _opration_names
from .._models import DesiredState
from .._redis import RedisServiceStateManager
from ._common_steps import RegisterScheduleId, UnRegisterScheduleId

_logger = logging.getLogger(__name__)


class _Prepare(BaseStep):
    """
    Figures if a service is legacy or not,
    only if it was not previously detenrimined
    """

    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id", "is_legacy"}

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {"is_legacy"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        node_id: NodeID = required_context["node_id"]
        is_legacy: bool | None = required_context["is_legacy"]

        # allows to skip lengthy check
        if is_legacy is not None:
            return {"is_legacy": is_legacy}

        # TODO: this will be done in a future PR, for now it stays mocked
        is_legacy = True

        return {"is_legacy": is_legacy}


class _Enforce(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id", "is_legacy"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        node_id: NodeID = required_context["node_id"]
        is_legacy: bool = required_context["is_legacy"]

        service_state_manager = RedisServiceStateManager(app=app, node_id=node_id)

        desired_state = await service_state_manager.read("desired_state")
        assert desired_state is not None  # nosec
        current_state = await service_state_manager.read("current_state")

        monitor_name = (
            _opration_names.LEGACY_MONITOR
            if is_legacy
            else _opration_names.NEW_STYLE_MONITOR
        )
        start_name = (
            _opration_names.LEGACY_START
            if is_legacy
            else _opration_names.NEW_STYLE_START
        )
        stop_name = (
            _opration_names.LEGACY_STOP if is_legacy else _opration_names.NEW_STYLE_STOP
        )

        initial_context = {"node_id": node_id}
        enforce_operation = OperationToStart(
            _opration_names.ENFORCE, initial_context=initial_context
        )

        if current_state == desired_state == DesiredState.RUNNING:
            await start_operation(
                app,
                monitor_name,
                initial_context,
                on_execute_completed=enforce_operation,
                on_revert_completed=enforce_operation,
            )
            return None

        if current_state == desired_state == DesiredState.STOPPED:
            # do nothing reached the end of everything just remove
            await service_state_manager.delete()
            _logger.debug("node_di='%s' removed from tracking", node_id)
            return None

        match desired_state:
            case DesiredState.RUNNING:
                await start_operation(
                    app,
                    start_name,
                    initial_context,
                    on_execute_completed=enforce_operation,
                    on_revert_completed=enforce_operation,
                )
            case DesiredState.STOPPED:
                await start_operation(
                    app,
                    stop_name,
                    initial_context,
                    on_execute_completed=enforce_operation,
                    on_revert_completed=enforce_operation,
                )

        return None


operation = Operation(
    SingleStepGroup(RegisterScheduleId),
    SingleStepGroup(_Prepare),
    SingleStepGroup(_Enforce),
    SingleStepGroup(UnRegisterScheduleId),
)
