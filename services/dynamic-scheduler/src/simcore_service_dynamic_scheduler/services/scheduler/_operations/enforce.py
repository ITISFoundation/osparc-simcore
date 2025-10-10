from fastapi import FastAPI

from ...generic_scheduler import (
    BaseStep,
    ProvidedOperationContext,
    RequiredOperationContext,
)


class _SEnforce(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        sad_thing: str | None = required_context["node_id"]

        # what if a key is not present in the context, it can be set to None in the initial context and we rxpect it to be None

        pass
