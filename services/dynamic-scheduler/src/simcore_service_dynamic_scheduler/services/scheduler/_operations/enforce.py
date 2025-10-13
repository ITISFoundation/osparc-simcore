from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID

from ...generic_scheduler import (
    BaseStep,
    Operation,
    ProvidedOperationContext,
    RequiredOperationContext,
    SingleStepGroup,
)
from ._common_steps import RegisterScheduleId, UnRegisterScheduleId


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


class _SEnforce(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        node_id: NodeID = required_context["node_id"]
        is_legacy: bool = required_context["is_legacy"]

        # do somehting here based on desired state or not
        # TODO: implement here


operation = Operation(
    SingleStepGroup(RegisterScheduleId),
    SingleStepGroup(_Prepare),
    SingleStepGroup(_SEnforce),
    SingleStepGroup(UnRegisterScheduleId),
)
