from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def send_message(
    app: FastAPI,
):
    assert app  # nosec
    raise NotImplementedError
