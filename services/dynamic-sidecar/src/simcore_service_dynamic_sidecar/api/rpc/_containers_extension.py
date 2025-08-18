from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...modules.inputs import disable_inputs_pulling, enable_inputs_pulling
from ...services.outputs import disable_event_propagation, enable_event_propagation

router = RPCRouter()


@router.expose()
async def toggle_ports_io(
    app: FastAPI, *, enable_outputs: bool, enable_inputs: bool
) -> None:
    if enable_outputs:
        await enable_event_propagation(app)
    else:
        await disable_event_propagation(app)

    if enable_inputs:
        enable_inputs_pulling(app)
    else:
        disable_inputs_pulling(app)
