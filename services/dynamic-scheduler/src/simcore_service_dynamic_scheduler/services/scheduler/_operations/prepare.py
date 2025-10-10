from fastapi import FastAPI

from ...generic_scheduler import (
    BaseStep,
    ProvidedOperationContext,
    RequiredOperationContext,
)


class _SPrepare(BaseStep):
    @classmethod
    def get_execute_requires_context_keys(cls) -> set[str]:
        return {"node_id"}

    @classmethod
    def get_execute_provides_context_keys(cls) -> set[str]:
        """
        [optional] keys that will be added to the OperationContext when EXECUTE is successful
        """
        return {"is_legacy"}

    @classmethod
    async def execute(
        cls, app: FastAPI, required_context: RequiredOperationContext
    ) -> ProvidedOperationContext | None:
        _ = app
        # what if a key is not present in the context, it can be set to None in the initial context and we rxpect it to be None
        sad_thing: str | None = required_context["node_id"]

        # setup all the required stuff that Enforce needs like the labels and all requuired data to be fetched


# TODO: might need a step to be reused for moving to the next operation by a given name
