from fastapi import FastAPI
from pydantic import BaseModel, Field


class InputsState(BaseModel):
    inputs_pulling_enabled: bool = Field(
        default=False, description="can pull input ports"
    )


def enable_inputs_state_pulling(app: FastAPI) -> None:
    inputs_state: InputsState = app.state.inputs_state
    inputs_state.inputs_pulling_enabled = True


def disable_inputs_state_pulling(app: FastAPI) -> None:
    inputs_state: InputsState = app.state.inputs_state
    inputs_state.inputs_pulling_enabled = False


def setup_inputs(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.inputs_state = InputsState()

    app.add_event_handler("startup", on_startup)
