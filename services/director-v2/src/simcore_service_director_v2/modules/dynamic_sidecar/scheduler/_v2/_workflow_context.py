from typing import Any, Optional

from fastapi import FastAPI

from ._context_base import ContextInterface, ContextIOInterface, ReservedContextKeys
from ._errors import (
    GetTypeMismatchError,
    NotAllowedContextKeyError,
    NotInContextError,
    SetTypeMismatchError,
)
from ._models import ActionName, WorkflowName


def _ensure_type_matches(key: str, existing_value: Any, value: Any) -> None:
    # if a value previously existed, ensure it has a compatible type
    existing_type = type(existing_value)
    value_type = type(value)
    if not isinstance(existing_value, value_type):
        raise SetTypeMismatchError(
            key=key,
            existing_value=existing_value,
            existing_type=existing_type,
            new_value=value,
            new_type=value_type,
        )


class WorkflowContext(ContextIOInterface):
    """
    Data container responsible for keeping track of the state of a workflow.
    """

    def __init__(
        self,
        context: ContextInterface,
        app: FastAPI,
        workflow_name: WorkflowName,
        action_name: ActionName,
    ) -> None:
        self._context = context
        self._app = app
        self._workflow_name = workflow_name
        self._action_name = action_name

        self._local_storage: dict[str, Any] = {}

    async def set(self, key: str, value: Any, *, set_reserved: bool = False) -> None:
        """
        Stores a value.
        NOTE: the type of the value is deduced the first time this was set.
        """
        if key in ReservedContextKeys.RESERVED and not set_reserved:
            raise NotAllowedContextKeyError(key=key)

        if key in ReservedContextKeys.STORED_LOCALLY:
            if key in self._local_storage:
                _ensure_type_matches(
                    key=key, existing_value=self._local_storage[key], value=value
                )
            self._local_storage[key] = value
        else:
            if await self._context.has_key(key):
                _ensure_type_matches(
                    key=key, existing_value=await self._context.load(key), value=value
                )
            await self._context.save(key, value)

    async def get(self, key: str, expected_type: type) -> Optional[Any]:
        """
        Loads a value. Raises an error if value is missing.
        """
        if (
            key not in ReservedContextKeys.STORED_LOCALLY
            and not await self._context.has_key(key)
        ):
            raise NotInContextError(key=key, context=await self._context.to_dict())

        existing_value = (
            self._local_storage[key]
            if key in ReservedContextKeys.STORED_LOCALLY
            else await self._context.load(key)
        )
        exiting_type = type(existing_value)
        if not isinstance(existing_value, expected_type):
            raise GetTypeMismatchError(
                key=key,
                existing_value=existing_value,
                existing_type=exiting_type,
                expected_type=expected_type,
            )
        return existing_value

    async def to_dict(self) -> dict[str, Any]:
        return await self._context.to_dict()

    @classmethod
    async def from_dict(
        cls, context: ContextInterface, app: FastAPI, incoming: dict[str, Any]
    ) -> "WorkflowContext":
        for key, value in incoming.items():
            await context.save(key, value)
        workflow_context = cls(
            context=context,
            app=app,
            workflow_name=incoming[ReservedContextKeys.WORKFLOW_NAME],
            action_name=incoming[ReservedContextKeys.WORKFLOW_ACTION_NAME],
        )
        await workflow_context.setup()
        return workflow_context

    async def setup(self) -> None:
        # adding app to context
        await self.set(key=ReservedContextKeys.APP, value=self._app, set_reserved=True)
        await self.set(
            key=ReservedContextKeys.WORKFLOW_NAME,
            value=self._workflow_name,
            set_reserved=True,
        )
        await self.set(
            key=ReservedContextKeys.WORKFLOW_ACTION_NAME,
            value=self._action_name,
            set_reserved=True,
        )
        await self.set(
            ReservedContextKeys.WORKFLOW_CURRENT_STEP_INDEX, 0, set_reserved=True
        )

    async def teardown(self) -> None:
        """no code required here"""
