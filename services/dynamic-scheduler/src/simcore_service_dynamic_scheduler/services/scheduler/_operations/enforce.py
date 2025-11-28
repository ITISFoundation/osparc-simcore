import logging

from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ...generic_scheduler import (
    BaseStep,
    Operation,
    OperationContext,
    OperationToStart,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
    start_operation,
)
from .. import _opration_names
from .._models import DesiredState, SchedulingProfileType
from .._redis import RedisServiceStateManager
from ._common_steps import SetCurrentScheduleId
from ._profiles import RegsteredSchedulingProfiles

_logger = logging.getLogger(__name__)


class _CacheSchedulingProfileType(BaseStep):
    """
    Computes and stores the scheduling profile to be used when enforcing
    """

    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id", "scheduling_profile_type"}

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        return {"scheduling_profile_type"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        node_id: NodeID = required_context["node_id"]
        scheduling_profile_type: SchedulingProfileType | None = required_context[
            "scheduling_profile_type"
        ]

        # allows to skip lengthy check
        if scheduling_profile_type is not None:
            return {"scheduling_profile_type": scheduling_profile_type}

        # TODO: this will be done in a future PR, for now it stays mocked
        _ = app
        _ = node_id
        scheduling_profile_type = SchedulingProfileType.LEGACY

        return {"scheduling_profile_type": scheduling_profile_type}


def _get_start_monitor_stop_initial_context(node_id: NodeID) -> OperationContext:
    return {"node_id": node_id}


class _Enforce(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id", "scheduling_profile_type"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        node_id: NodeID = required_context["node_id"]
        scheduling_profile_type: SchedulingProfileType = required_context[
            "scheduling_profile_type"
        ]

        service_state_manager = RedisServiceStateManager(app=app, node_id=node_id)

        desired_state = await service_state_manager.read("desired_state")
        assert desired_state is not None  # nosec
        current_state = await service_state_manager.read("current_state")

        profile = RegsteredSchedulingProfiles.get_profile(scheduling_profile_type)

        initial_context = _get_start_monitor_stop_initial_context(node_id)
        enforce_operation = OperationToStart(
            _opration_names.ENFORCE, initial_context=initial_context
        )

        _logger.debug(
            "Deciding based on current='%s' and desired='%s'",
            current_state,
            desired_state,
        )

        if current_state == desired_state == DesiredState.RUNNING:
            await start_operation(
                app,
                profile.monitor_name,
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
                    profile.start_name,
                    initial_context,
                    on_execute_completed=enforce_operation,
                    on_revert_completed=enforce_operation,
                )
            case DesiredState.STOPPED:
                await start_operation(
                    app,
                    profile.stop_name,
                    initial_context,
                    on_execute_completed=enforce_operation,
                    on_revert_completed=enforce_operation,
                )

        return None


def get_operation() -> Operation:
    return Operation(
        SingleStepGroup(SetCurrentScheduleId),
        SingleStepGroup(_CacheSchedulingProfileType),
        SingleStepGroup(_Enforce),
    )
