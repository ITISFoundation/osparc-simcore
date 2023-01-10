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
    # if a value previously existed,
    # ensure it has the same type
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
    Data container responsible for keeping track of the state of a play.
    """

    def __init__(
        self,
        context: ContextInterface,
        app: FastAPI,
        play_name: WorkflowName,
        action_name: ActionName,
    ) -> None:
        self._context = context
        self._app = app
        self._play_name = play_name
        self._action_name = action_name

        self._local_storage: dict[str, Any] = {}

    async def set(self, key: str, value: Any, *, set_reserved: bool = False) -> None:
        """
        Saves a value. Note the type of the value is forced
        at the same type as the first time this was set.

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
        returns an existing value ora raises an error
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

    async def from_dict(self, incoming: dict[str, Any]) -> None:
        return await self._context.from_dict(incoming)

    async def setup(self) -> None:
        # adding app to context
        await self.set(key=ReservedContextKeys.APP, value=self._app, set_reserved=True)
        await self.set(
            key=ReservedContextKeys.PLAY_NAME, value=self._play_name, set_reserved=True
        )
        await self.set(
            key=ReservedContextKeys.PLAY_ACTION_NAME,
            value=self._action_name,
            set_reserved=True,
        )
        await self.set(
            ReservedContextKeys.PLAY_CURRENT_STEP_INDEX, 0, set_reserved=True
        )

    async def teardown(self) -> None:
        """nothing code required here"""
