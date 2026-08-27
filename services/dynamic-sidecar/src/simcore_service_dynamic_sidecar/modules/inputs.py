from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from pydantic import BaseModel, Field


class InputsState(BaseModel):
    inputs_pulling_enabled: bool = Field(default=False, description="can pull input ports")


def enable_inputs_pulling(app: FastAPI) -> None:
    inputs_state: InputsState = app.state.inputs_state
    inputs_state.inputs_pulling_enabled = True


def disable_inputs_pulling(app: FastAPI) -> None:
    inputs_state: InputsState = app.state.inputs_state
    inputs_state.inputs_pulling_enabled = False


async def _inputs_lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.inputs_state = InputsState()
    yield


def configure_inputs(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_inputs_lifespan)
