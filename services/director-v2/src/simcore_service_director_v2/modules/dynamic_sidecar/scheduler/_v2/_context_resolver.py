from typing import Any, Optional

from fastapi import FastAPI

from ._context_base import (
    BaseContextInterface,
    ContextIOInterface,
    ContextStorageInterface,
    ReservedContextKeys,
)
from ._errors import (
    GetTypeMismatchError,
    NotAllowedContextKeyError,
    NotInContextError,
    SetTypeMismatchError,
)
from ._models import StateName, WorkflowName


class ContextResolver(ContextIOInterface):
    """
    Used to keep track of generated data.
    """

    def __init__(
        self,
        storage_context: type[BaseContextInterface],
        app: FastAPI,
        workflow_name: WorkflowName,
        state_name: StateName,
    ) -> None:
        self._app: FastAPI = app
        self._workflow_name: WorkflowName = workflow_name
        self._state_name: StateName = state_name

        self._context: ContextStorageInterface = storage_context()

        self._local_storage: dict[str, Any] = {}

    async def set(self, key: str, value: Any, *, set_reserved: bool = False) -> None:
        """
        Saves a value. Note the type of the value is forced
        at the same type as the first time this was set.

        """
        if key in ReservedContextKeys.RESERVED and not set_reserved:
            raise NotAllowedContextKeyError(key=key)

        def ensure_type_matches(existing_value: Any, value: Any) -> None:
            # if a value previously existed,
            # ensure it has the same type
            existing_type = type(existing_value)
            value_type = type(value)
            if existing_type != value_type:
                raise SetTypeMismatchError(
                    key=key,
                    existing_value=existing_value,
                    existing_type=existing_type,
                    new_value=value,
                    new_type=value_type,
                )

        if key in ReservedContextKeys.STORED_LOCALLY:
            if key in self._local_storage:
                ensure_type_matches(
                    existing_value=self._local_storage[key], value=value
                )
            self._local_storage[key] = value
        else:
            if await self._context.has_key(key):
                ensure_type_matches(
                    existing_value=await self._context.load(key), value=value
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
        if exiting_type != expected_type:
            raise GetTypeMismatchError(
                key=key,
                existing_value=existing_value,
                exiting_type=exiting_type,
                expected_type=expected_type,
            )
        return existing_value

    async def to_dict(self) -> dict[str, Any]:
        return await self._context.to_dict()

    async def from_dict(self, incoming: dict[str, Any]) -> None:
        return await self._context.from_dict(incoming)

    async def start(self) -> None:
        await self._context.start()
        # adding app to context
        await self.set(key=ReservedContextKeys.APP, value=self._app, set_reserved=True)
        await self.set(
            key=ReservedContextKeys.WORKFLOW_NAME,
            value=self._workflow_name,
            set_reserved=True,
        )
        await self.set(
            key=ReservedContextKeys.WORKFLOW_STATE_NAME,
            value=self._state_name,
            set_reserved=True,
        )

    async def shutdown(self) -> None:
        await self._context.shutdown()
