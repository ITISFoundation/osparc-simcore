from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...services import long_running_tasks

router = RPCRouter()


@router.expose()
async def cleanup_local_long_running_tasks(app: FastAPI) -> None:
    await long_running_tasks.cleanup_long_running_tasks(app)
