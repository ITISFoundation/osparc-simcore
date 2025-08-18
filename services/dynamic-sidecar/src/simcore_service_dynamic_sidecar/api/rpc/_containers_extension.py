from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...services import container_extensions

router = RPCRouter()


@router.expose()
async def toggle_ports_io(
    app: FastAPI, *, enable_outputs: bool, enable_inputs: bool
) -> None:
    await container_extensions.toggle_ports_io(
        app, enable_outputs=enable_outputs, enable_inputs=enable_inputs
    )
