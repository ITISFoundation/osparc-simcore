from fastapi import FastAPI
from pydantic import NonNegativeInt
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def get_max_workers(app: FastAPI) -> int:
    return 1


@router.expose()
async def set_max_workers(app: FastAPI, *, num_workers: NonNegativeInt) -> None:
    ...
